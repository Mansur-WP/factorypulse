"""
Automated tests for the Africa's Talking SMS Service.
All Africa's Talking API calls are mocked to avoid external network dependencies.
"""

from unittest.mock import patch, MagicMock, call
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import FaultReport, Technician, Machine

User = get_user_model()


class SMSServiceUnitTests(TestCase):
    """Unit tests for ussd.sms_service functions."""

    def setUp(self):
        Technician.objects.all().delete()
        Machine.objects.all().delete()

        self.tech_user = User.objects.create_user(
            username='tech_sms', password='testpass', is_staff=False
        )
        self.technician = Technician.objects.create(
            user=self.tech_user,
            name='SMS Test Tech',
            phone_number='+2349012345678',
        )
        self.machine = Machine.objects.create(name='SMS Test Machine')
        self.fault = FaultReport.objects.create(
            phone_number='+2340000000001',
            machine=str(self.machine),
            problem='Overheating',
            severity='high',
            status=FaultReport.STATUS_OPEN,
        )

    # ------------------------------------------------------------------ #
    # send_sms — low-level helper (uses http.client, not AT SDK)             #
    # ------------------------------------------------------------------ #

    @patch('ussd.sms_service.http.client.HTTPSConnection')
    def test_send_sms_calls_api_with_correct_args(self, mock_conn_cls):
        """send_sms should POST to AT API with the right phone and message."""
        from .sms_service import send_sms

        # Set up mock connection and response
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn
        mock_resp = MagicMock()
        mock_resp.status = 201
        mock_resp.read.return_value = b'{"SMSMessageData": {"Message": "Sent to 1/1", "Recipients": [{"status": "Success", "statusCode": 101, "messageId": "ATXid_123"}]}}'
        mock_conn.getresponse.return_value = mock_resp

        result = send_sms('+2349012345678', 'Hello Technician')

        mock_conn.request.assert_called_once()
        call_args = mock_conn.request.call_args
        self.assertEqual(call_args[0][0], 'POST')  # method
        self.assertIn('/version1/messaging', call_args[0][1])  # path
        # body is passed as keyword arg to conn.request()
        body = call_args[1].get('body', '')
        self.assertIn('to=%2B2349012345678', body)  # phone in body
        self.assertEqual(result['status'], 'sent')

    def test_send_sms_empty_phone_skipped(self):
        """send_sms should skip and return 'skipped' if recipient is empty."""
        from .sms_service import send_sms

        result = send_sms('', 'Test message')
        self.assertEqual(result['status'], 'skipped')

    @patch('ussd.sms_service._get_at_config')
    def test_send_sms_no_api_key_skipped(self, mock_config):
        """send_sms should skip gracefully if AT API key is not configured."""
        from .sms_service import send_sms

        mock_config.return_value = {'username': 'sandbox', 'api_key': ''}
        result = send_sms('+2349012345678', 'Hello')
        self.assertEqual(result['status'], 'skipped')

    @patch('ussd.sms_service.http.client.HTTPSConnection')
    def test_send_sms_api_failure_returns_failed(self, mock_conn_cls):
        """send_sms should catch API exceptions and return {'status': 'failed'}."""
        from .sms_service import send_sms

        mock_conn_cls.return_value.request.side_effect = Exception("Network timeout")

        result = send_sms('+2349012345678', 'Hello')
        self.assertEqual(result['status'], 'failed')
        self.assertIn('error', result)

    # ------------------------------------------------------------------ #
    # send_technician_assignment_sms                                        #
    # ------------------------------------------------------------------ #

    @patch('ussd.sms_service.send_sms')
    def test_assignment_sms_sent_to_correct_phone(self, mock_send_sms):
        """send_technician_assignment_sms should send to the technician's phone number."""
        from .sms_service import send_technician_assignment_sms

        mock_send_sms.return_value = {'status': 'sent'}
        send_technician_assignment_sms(self.fault, self.technician)

        mock_send_sms.assert_called_once()
        args = mock_send_sms.call_args[0]
        self.assertEqual(args[0], '+2349012345678')

    @patch('ussd.sms_service.send_sms')
    def test_assignment_sms_contains_fault_info(self, mock_send_sms):
        """send_technician_assignment_sms should include fault ID, machine, problem, severity."""
        from .sms_service import send_technician_assignment_sms

        mock_send_sms.return_value = {'status': 'sent'}
        send_technician_assignment_sms(self.fault, self.technician)

        message = mock_send_sms.call_args[0][1]
        self.assertIn(str(self.fault.id), message)
        self.assertIn(self.fault.machine, message)
        self.assertIn(self.fault.problem, message)
        self.assertIn('HIGH', message)

    @patch('ussd.sms_service.send_sms')
    def test_assignment_sms_skipped_if_no_phone(self, mock_send_sms):
        """send_technician_assignment_sms should NOT call send_sms if technician has no phone."""
        from .sms_service import send_technician_assignment_sms

        self.technician.phone_number = ''
        self.technician.save()

        result = send_technician_assignment_sms(self.fault, self.technician)
        mock_send_sms.assert_not_called()
        self.assertFalse(result)

    @patch('ussd.sms_service.send_sms')
    def test_assignment_sms_skipped_if_technician_is_none(self, mock_send_sms):
        """send_technician_assignment_sms should be a safe no-op if technician is None."""
        from .sms_service import send_technician_assignment_sms

        result = send_technician_assignment_sms(self.fault, None)
        mock_send_sms.assert_not_called()
        self.assertFalse(result)


class SMSIntegrationWithAssignmentTests(TestCase):
    """
    Integration tests: SMS service is triggered through assign_fault_to_technician.
    All Africa's Talking API calls are fully mocked.
    """

    def setUp(self):
        Technician.objects.all().delete()
        Machine.objects.all().delete()

        self.supervisor = User.objects.create_user(
            username='supervisor_sms', password='testpass', is_staff=True
        )
        self.tech_user = User.objects.create_user(
            username='tech_assign_sms', password='testpass', is_staff=False
        )
        self.technician = Technician.objects.create(
            user=self.tech_user,
            name='Integration Tech',
            phone_number='+2349098765432',
        )
        self.machine = Machine.objects.create(name='Sms Machine')
        self.fault = FaultReport.objects.create(
            phone_number='+2340000000002',
            machine=str(self.machine),
            problem='Making noise',
            severity='medium',
            status=FaultReport.STATUS_OPEN,
        )

    @patch('ussd.sms_service.send_sms')
    def test_assigning_technician_triggers_sms(self, mock_send_sms):
        """assign_fault_to_technician should trigger send_sms after a successful DB save."""
        from .services import assign_fault_to_technician

        mock_send_sms.return_value = {'status': 'sent'}
        assign_fault_to_technician(self.fault.id, self.tech_user)

        mock_send_sms.assert_called_once()

    @patch('ussd.sms_service.send_sms')
    def test_assignment_uses_technician_phone(self, mock_send_sms):
        """SMS should be sent to the correct technician phone number."""
        from .services import assign_fault_to_technician

        mock_send_sms.return_value = {'status': 'sent'}
        assign_fault_to_technician(self.fault.id, self.tech_user)

        recipient = mock_send_sms.call_args[0][0]
        self.assertEqual(recipient, '+2349098765432')

    @patch('ussd.sms_service.send_sms')
    def test_sms_not_sent_when_assignment_fails(self, mock_send_sms):
        """SMS must NOT be sent when fault assignment raises a ValidationError."""
        from .services import assign_fault_to_technician

        self.fault.status = FaultReport.STATUS_RESOLVED
        self.fault.save()

        with self.assertRaises(ValidationError):
            assign_fault_to_technician(self.fault.id, self.tech_user)

        mock_send_sms.assert_not_called()

    @patch('ussd.sms_service.send_sms')
    def test_sms_failure_does_not_roll_back_assignment(self, mock_send_sms):
        """A crash in the SMS layer must NOT undo the fault assignment in the DB."""
        from .services import assign_fault_to_technician

        mock_send_sms.side_effect = Exception("Africa's Talking API unreachable")

        # Should not raise — the exception is caught inside services.py
        assign_fault_to_technician(self.fault.id, self.tech_user)

        # DB state must still reflect the assignment
        self.fault.refresh_from_db()
        self.assertEqual(self.fault.status, FaultReport.STATUS_ASSIGNED)
        self.assertEqual(self.fault.assigned_to, self.tech_user)

    @patch('ussd.sms_service.send_sms')
    def test_sms_not_sent_for_non_technician_user(self, mock_send_sms):
        """No SMS if the user is not registered as a technician."""
        from .services import assign_fault_to_technician

        random_user = User.objects.create_user(username='random_guy', password='x')

        with self.assertRaises(ValidationError):
            assign_fault_to_technician(self.fault.id, random_user)

        mock_send_sms.assert_not_called()


class SMSDeliveryCallbackTests(TestCase):
    """Tests for the Africa's Talking SMS Delivery Status webhook."""

    def setUp(self):
        self.client = Client()

    def test_delivery_callback_returns_200(self):
        """POST /sms/delivery/ should return HTTP 200 OK."""
        response = self.client.post('/sms/delivery/', {
            'id': 'ATXid123',
            'status': 'Success',
            'phoneNumber': '+2349012345678',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'OK')

    def test_delivery_callback_failure_status_returns_200(self):
        """POST /sms/delivery/ with a failed status should still return 200 (never drop Africa's Talking)."""
        response = self.client.post('/sms/delivery/', {
            'id': 'ATXid456',
            'status': 'Failed',
            'phoneNumber': '+2349012345678',
            'failureReason': 'InsufficientCredit',
        })
        self.assertEqual(response.status_code, 200)

    def test_delivery_callback_rejects_get(self):
        """GET /sms/delivery/ should be rejected (405 Method Not Allowed)."""
        response = self.client.get('/sms/delivery/')
        self.assertEqual(response.status_code, 405)


class IncomingSMSResponseTests(TestCase):
    """
    Tests for the Technician SMS Response Workflow (POST /sms/incoming/).
    Covers ACCEPT, START, RESOLVE commands, phone matching, state rules, security & error responses.
    """

    def setUp(self):
        Technician.objects.all().delete()
        Machine.objects.all().delete()
        self.client = Client()

        # Users & Technicians
        self.user_tech_1 = User.objects.create_user(username='tech1_sms', password='pass')
        self.tech_1 = Technician.objects.create(
            user=self.user_tech_1,
            name='Musa Tech',
            phone_number='+2348011112222'
        )

        self.user_tech_2 = User.objects.create_user(username='tech2_sms', password='pass')
        self.tech_2 = Technician.objects.create(
            user=self.user_tech_2,
            name='Abdullahi Tech',
            phone_number='+2348033334444'
        )

        self.machine = Machine.objects.create(name='Generator')

        # Assigned fault to tech_1
        self.fault_assigned = FaultReport.objects.create(
            machine=str(self.machine),
            problem='Overheating',
            severity='High',
            status=FaultReport.STATUS_ASSIGNED,
            assigned_to=self.user_tech_1,
        )

    @patch('ussd.sms_service.send_sms')
    def test_technician_sends_accept(self, mock_send_sms):
        """Technician sending ACCEPT <id> updates status to ACCEPTED and sends confirmation."""
        mock_send_sms.return_value = {'status': 'sent'}

        response = self.client.post('/sms/incoming/', {
            'from': '+2348011112222',
            'to': '20880',
            'text': f'ACCEPT {self.fault_assigned.id}',
            'date': '2026-08-29 14:00:00',
            'id': 'ATX1001',
        })
        self.assertEqual(response.status_code, 200)

        self.fault_assigned.refresh_from_db()
        self.assertEqual(self.fault_assigned.status, FaultReport.STATUS_ACCEPTED)

        # Check confirmation SMS sent to technician
        mock_send_sms.assert_called_once()
        recipient, message = mock_send_sms.call_args[0]
        self.assertEqual(recipient, '+2348011112222')
        self.assertIn(f'Fault #{self.fault_assigned.id} accepted', message)

    @patch('ussd.sms_service.send_sms')
    def test_technician_sends_start(self, mock_send_sms):
        """Technician sending START <id> updates status from ACCEPTED to IN_PROGRESS."""
        mock_send_sms.return_value = {'status': 'sent'}
        self.fault_assigned.status = FaultReport.STATUS_ACCEPTED
        self.fault_assigned.save()

        response = self.client.post('/sms/incoming/', {
            'from': '+2348011112222',
            'to': '20880',
            'text': f'START {self.fault_assigned.id}',
            'date': '2026-08-29 14:05:00',
            'id': 'ATX1002',
        })
        self.assertEqual(response.status_code, 200)

        self.fault_assigned.refresh_from_db()
        self.assertEqual(self.fault_assigned.status, FaultReport.STATUS_IN_PROGRESS)

        message = mock_send_sms.call_args[0][1]
        self.assertIn('IN PROGRESS', message)

    @patch('ussd.sms_service.send_sms')
    def test_technician_sends_resolve(self, mock_send_sms):
        """Technician sending RESOLVE <id> updates status from IN_PROGRESS to RESOLVED."""
        mock_send_sms.return_value = {'status': 'sent'}
        self.fault_assigned.status = FaultReport.STATUS_IN_PROGRESS
        self.fault_assigned.save()

        response = self.client.post('/sms/incoming/', {
            'from': '+2348011112222',
            'to': '20880',
            'text': f'RESOLVE {self.fault_assigned.id}',
            'date': '2026-08-29 14:10:00',
            'id': 'ATX1003',
        })
        self.assertEqual(response.status_code, 200)

        self.fault_assigned.refresh_from_db()
        self.assertEqual(self.fault_assigned.status, FaultReport.STATUS_RESOLVED)

        message = mock_send_sms.call_args[0][1]
        self.assertIn('RESOLVED', message)

    @patch('ussd.sms_service.send_sms')
    def test_lowercase_and_spaced_commands(self, mock_send_sms):
        """Commands are case-insensitive and handle extra spaces."""
        mock_send_sms.return_value = {'status': 'sent'}

        response = self.client.post('/sms/incoming/', {
            'from': '+2348011112222',
            'text': f'   accept    {self.fault_assigned.id}   ',
        })
        self.assertEqual(response.status_code, 200)

        self.fault_assigned.refresh_from_db()
        self.assertEqual(self.fault_assigned.status, FaultReport.STATUS_ACCEPTED)

    @patch('ussd.sms_service.send_sms')
    def test_invalid_command_returns_helpful_response(self, mock_send_sms):
        """Invalid command text triggers an instructional reply."""
        mock_send_sms.return_value = {'status': 'sent'}

        response = self.client.post('/sms/incoming/', {
            'from': '+2348011112222',
            'text': 'FIX 9',
        })
        self.assertEqual(response.status_code, 200)

        message = mock_send_sms.call_args[0][1]
        self.assertIn('Invalid command', message)
        self.assertIn('ACCEPT <fault ID>', message)

    @patch('ussd.sms_service.send_sms')
    def test_missing_or_non_numeric_fault_id(self, mock_send_sms):
        """Missing or non-numeric fault ID triggers an invalid command reply."""
        mock_send_sms.return_value = {'status': 'sent'}

        self.client.post('/sms/incoming/', {
            'from': '+2348011112222',
            'text': 'ACCEPT abc',
        })
        message = mock_send_sms.call_args[0][1]
        self.assertIn('Invalid command', message)

    @patch('ussd.sms_service.send_sms')
    def test_nonexistent_fault(self, mock_send_sms):
        """Nonexistent fault ID returns fault not found message."""
        mock_send_sms.return_value = {'status': 'sent'}

        self.client.post('/sms/incoming/', {
            'from': '+2348011112222',
            'text': 'ACCEPT 999999',
        })
        message = mock_send_sms.call_args[0][1]
        self.assertIn('Fault #999999 not found', message)

    @patch('ussd.sms_service.send_sms')
    def test_unregistered_phone_number(self, mock_send_sms):
        """Sender not matching any Technician gets a safe error reply and no fault change."""
        mock_send_sms.return_value = {'status': 'sent'}

        self.client.post('/sms/incoming/', {
            'from': '+2349999999999',
            'text': f'ACCEPT {self.fault_assigned.id}',
        })

        self.fault_assigned.refresh_from_db()
        self.assertEqual(self.fault_assigned.status, FaultReport.STATUS_ASSIGNED)

        message = mock_send_sms.call_args[0][1]
        self.assertIn('not registered as a technician', message)

    @patch('ussd.sms_service.send_sms')
    def test_technician_cannot_modify_other_technicians_fault(self, mock_send_sms):
        """Technician 2 cannot modify a fault assigned to Technician 1."""
        mock_send_sms.return_value = {'status': 'sent'}

        response = self.client.post('/sms/incoming/', {
            'from': '+2348033334444',  # tech_2's phone
            'text': f'ACCEPT {self.fault_assigned.id}',  # assigned to tech_1
        })
        self.assertEqual(response.status_code, 200)

        self.fault_assigned.refresh_from_db()
        self.assertEqual(self.fault_assigned.status, FaultReport.STATUS_ASSIGNED)

        message = mock_send_sms.call_args[0][1]
        self.assertIn('is not assigned to you', message)

    @patch('ussd.sms_service.send_sms')
    def test_invalid_status_transitions(self, mock_send_sms):
        """Rejects invalid transitions such as OPEN -> START, ASSIGNED -> RESOLVE, RESOLVED -> START."""
        mock_send_sms.return_value = {'status': 'sent'}

        # 1. OPEN fault -> START
        fault_open = FaultReport.objects.create(
            machine='Generator',
            problem='Leaking oil',
            severity='Medium',
            status=FaultReport.STATUS_OPEN,
            assigned_to=self.user_tech_1,
        )
        self.client.post('/sms/incoming/', {
            'from': '+2348011112222',
            'text': f'START {fault_open.id}',
        })
        fault_open.refresh_from_db()
        self.assertEqual(fault_open.status, FaultReport.STATUS_OPEN)

        # 2. ASSIGNED fault -> RESOLVE
        self.client.post('/sms/incoming/', {
            'from': '+2348011112222',
            'text': f'RESOLVE {self.fault_assigned.id}',
        })
        self.fault_assigned.refresh_from_db()
        self.assertEqual(self.fault_assigned.status, FaultReport.STATUS_ASSIGNED)

        # 3. RESOLVED fault -> START
        self.fault_assigned.status = FaultReport.STATUS_RESOLVED
        self.fault_assigned.save()
        self.client.post('/sms/incoming/', {
            'from': '+2348011112222',
            'text': f'START {self.fault_assigned.id}',
        })
        self.fault_assigned.refresh_from_db()
        self.assertEqual(self.fault_assigned.status, FaultReport.STATUS_RESOLVED)

