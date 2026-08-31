import os
import sys
import importlib
from django.test import SimpleTestCase
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings, Settings

class SecurityConfigTests(SimpleTestCase):
    """Tests settings logic under various environments and configurations."""

    def setUp(self):
        self.original_env = dict(os.environ)
        self.original_wrapped = getattr(settings, '_wrapped', None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)
        if self.original_wrapped is not None:
            settings._wrapped = self.original_wrapped

    def reload_settings(self):
        """Forcefully reloads settings module and re-initializes Django settings wrapper."""
        if 'config.settings' in sys.modules:
            importlib.reload(sys.modules['config.settings'])
        settings._wrapped = Settings('config.settings')

    def test_development_defaults(self):
        """Verify that development mode sets up convenience defaults."""
        os.environ['DJANGO_ENV'] = 'development'
        os.environ['DEBUG'] = 'True'
        os.environ['DJANGO_SECRET_KEY'] = 'dev-key-123'
        os.environ['ALLOWED_HOSTS'] = ''

        self.reload_settings()

        self.assertTrue(settings.DEBUG)
        self.assertEqual(settings.SECRET_KEY, 'dev-key-123')
        self.assertIn('*', settings.ALLOWED_HOSTS)
        # Redirect settings should not be set or active in development mode
        self.assertFalse(getattr(settings, 'SECURE_SSL_REDIRECT', False))

    def test_production_requires_secret_key(self):
        """Verify that production fails fast when DJANGO_SECRET_KEY is absent."""
        os.environ['DJANGO_ENV'] = 'production'
        os.environ['DEBUG'] = 'False'
        os.environ['DJANGO_SECRET_KEY'] = ''
        os.environ['ALLOWED_HOSTS'] = 'example.com'

        with self.assertRaises(ImproperlyConfigured) as ctx:
            self.reload_settings()
        self.assertIn("DJANGO_SECRET_KEY environment variable is required in production", str(ctx.exception))

    def test_production_rejects_empty_allowed_hosts(self):
        """Verify that production fails fast when ALLOWED_HOSTS is empty."""
        os.environ['DJANGO_ENV'] = 'production'
        os.environ['DEBUG'] = 'False'
        os.environ['DJANGO_SECRET_KEY'] = 'some-prod-secret'
        os.environ['ALLOWED_HOSTS'] = ''

        with self.assertRaises(ImproperlyConfigured) as ctx:
            self.reload_settings()
        self.assertIn("ALLOWED_HOSTS cannot be empty in production", str(ctx.exception))

    def test_production_rejects_wildcard_allowed_hosts(self):
        """Verify that production fails fast when ALLOWED_HOSTS contains a wildcard."""
        os.environ['DJANGO_ENV'] = 'production'
        os.environ['DEBUG'] = 'False'
        os.environ['DJANGO_SECRET_KEY'] = 'some-prod-secret'
        os.environ['ALLOWED_HOSTS'] = 'example.com,*'

        with self.assertRaises(ImproperlyConfigured) as ctx:
            self.reload_settings()
        self.assertIn("ALLOWED_HOSTS cannot contain wildcard '*' in production", str(ctx.exception))

    def test_production_enables_secure_settings(self):
        """Verify that production mode turns on HTTP/HTTPS protection flags."""
        os.environ['DJANGO_ENV'] = 'production'
        os.environ['DEBUG'] = 'False'
        os.environ['DJANGO_SECRET_KEY'] = 'some-prod-secret-key-1234'
        os.environ['ALLOWED_HOSTS'] = 'example.com'

        self.reload_settings()

        self.assertFalse(settings.DEBUG)
        self.assertTrue(settings.SECURE_SSL_REDIRECT)
        self.assertTrue(settings.SESSION_COOKIE_SECURE)
        self.assertTrue(settings.CSRF_COOKIE_SECURE)
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertEqual(settings.X_FRAME_OPTIONS, 'DENY')
        self.assertEqual(settings.SECURE_REFERRER_POLICY, 'same-origin')
        self.assertEqual(settings.SECURE_HSTS_SECONDS, 31536000)
        self.assertTrue(settings.SECURE_HSTS_INCLUDE_SUBDOMAINS)
        self.assertTrue(settings.SECURE_HSTS_PRELOAD)


from django.test import TestCase, Client
from django.urls import reverse

class Phase1BSecurityFixTests(TestCase):
    """Focused unit tests for Phase 1B verified security fixes."""

    def setUp(self):
        self.client = Client()

    def test_open_redirect_rejected(self):
        """Verify that external domain redirect targets are rejected and fallback to dashboard_home."""
        response = self.client.get(reverse('dashboard_login') + '?next=https://evil-phishing-site.com')
        # Form field 'next_url' in context should sanitize out evil domain
        self.assertEqual(response.context['next_url'], '')

    def test_incoming_sms_webhook_secret_enforcement(self):
        """Verify that incoming SMS webhook rejects calls when webhook secret does not match."""
        url = reverse('sms_incoming_callback')
        
        # 1. When secret is configured in settings and incorrect secret provided -> 403 Forbidden
        with self.settings(AFRICASTALKING_WEBHOOK_SECRET='super-secret-webhook-key'):
            res_bad = self.client.post(url + '?secret=wrong-key', data={'from': '+2348012345678', 'text': 'ACCEPT 1'})
            self.assertEqual(res_bad.status_code, 403)
            self.assertIn('Forbidden', res_bad.content.decode())

            # Correct secret -> 200 OK
            res_good = self.client.post(url + '?secret=super-secret-webhook-key', data={'from': '+2348012345678', 'text': 'ACCEPT 1'})
            self.assertEqual(res_good.status_code, 200)


from ussd.models import FaultReport, Machine, Technician
from ussd.services import create_fault_report, process_incoming_technician_sms
from django.contrib.auth import get_user_model

User = get_user_model()

class Phase1CSecurityFixTests(TestCase):
    """Focused unit tests for Phase 1C input validation and endpoint hardening."""

    def setUp(self):
        self.client = Client()

    def test_create_fault_report_field_truncation(self):
        """Verify that excessively long strings are safely truncated to model column limits."""
        long_machine = "A" * 300
        long_problem = "B" * 500
        fault = create_fault_report(
            machine=long_machine,
            problem=long_problem,
            severity="High",
            phone_number="+2348012345678"
        )
        self.assertEqual(len(fault.machine), 100)
        self.assertEqual(len(fault.problem), 255)

    def test_process_incoming_sms_overflow_fault_id(self):
        """Verify that integer overflow or huge fault IDs in SMS commands do not crash the service."""
        user = User.objects.create_user(username='tech1', password='pass')
        Technician.objects.create(user=user, name='Tech 1', phone_number='+2348000000000')

        # Huge fault ID
        result = process_incoming_technician_sms('+2348000000000', 'ACCEPT 999999999999999999999999999')
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['reason'], 'invalid_fault_id')

    def test_machine_add_invalid_status_fallback(self):
        """Verify that submitting an invalid status during machine registration falls back to Operational."""
        from ussd.models import Factory, SupervisorProfile
        factory = Factory.objects.create(name='Test Factory For Phase1C')
        user = User.objects.create_user(username='staff', password='pass', is_staff=True)
        SupervisorProfile.objects.create(user=user, factory=factory)
        self.client.force_login(user)

        response = self.client.post(reverse('dashboard_machine_add'), {
            'name': 'New Testing Machine',
            'status': 'INVALID_HACKED_STATUS'
        })
        self.assertEqual(response.status_code, 302)
        machine = Machine.objects.get(name='New Testing Machine')
        self.assertEqual(machine.status, Machine.STATUS_OPERATIONAL)


from ussd.models import Factory, SupervisorProfile, FaultStatusHistory
from ussd.services import assign_fault_to_technician
from django.core.exceptions import ValidationError
from unittest.mock import patch

@patch('ussd.sms_service.send_sms')
@patch('ussd.sms_service.send_technician_assignment_sms')
class Phase3AccessControlTests(TestCase):
    """Focused unit tests for Phase 3 role-based access control, unassigned staff denial, and factory isolation."""

    def setUp(self):
        self.client = Client()
        self.factory_a = Factory.objects.create(name="Factory Alpha")
        self.factory_b = Factory.objects.create(name="Factory Beta")

        # Superuser (Global access)
        self.superuser = User.objects.create_superuser(username='superadmin', password='password123', email='admin@factory.com')

        # Factory A Supervisor
        self.sup_user_a = User.objects.create_user(username='sup_alpha', password='password123', is_staff=True)
        SupervisorProfile.objects.create(user=self.sup_user_a, factory=self.factory_a)

        # Factory B Supervisor
        self.sup_user_b = User.objects.create_user(username='sup_beta', password='password123', is_staff=True)
        SupervisorProfile.objects.create(user=self.sup_user_b, factory=self.factory_b)

        # Unassigned Staff (is_staff=True, is_superuser=False, no factory)
        self.unassigned_staff = User.objects.create_user(username='staff_unassigned', password='password123', is_staff=True)

        # Technician A (Factory A)
        self.tech_user_a = User.objects.create_user(username='tech_alpha', password='password123', is_staff=False)
        self.tech_a = Technician.objects.create(user=self.tech_user_a, name='Tech Alpha', phone_number='+2348111111111', factory=self.factory_a)

        # Technician B (Factory B)
        self.tech_user_b = User.objects.create_user(username='tech_beta', password='password123', is_staff=False)
        self.tech_b = Technician.objects.create(user=self.tech_user_b, name='Tech Beta', phone_number='+2348222222222', factory=self.factory_b)

        # Unassigned Technician (No factory)
        self.tech_user_unassigned = User.objects.create_user(username='tech_unassigned', password='password123', is_staff=False)
        self.tech_unassigned = Technician.objects.create(user=self.tech_user_unassigned, name='Tech Unassigned', phone_number='+2348333333333', factory=None)

        # Machines
        self.machine_a = Machine.objects.create(name="Alpha Generator", status="OPERATIONAL", factory=self.factory_a)
        self.machine_b = Machine.objects.create(name="Beta Generator", status="OPERATIONAL", factory=self.factory_b)

        # Faults
        self.fault_open_a = FaultReport.objects.create(
            machine="Alpha Machine 1",
            problem="Not working",
            severity="High",
            status=FaultReport.STATUS_OPEN,
            factory=self.factory_a
        )
        self.fault_a = FaultReport.objects.create(
            machine="Alpha Machine 1",
            problem="Overheating",
            severity="High",
            status=FaultReport.STATUS_ASSIGNED,
            assigned_to=self.tech_user_a,
            factory=self.factory_a
        )
        self.fault_b = FaultReport.objects.create(
            machine="Beta Machine 1",
            problem="Not working",
            severity="Medium",
            status=FaultReport.STATUS_ASSIGNED,
            assigned_to=self.tech_user_b,
            factory=self.factory_b
        )

    def test_unassigned_staff_cannot_access_dashboard(self, mock_assign_sms, mock_sms):
        """1. Verify unassigned non-superuser staff cannot access dashboard home."""
        self.client.force_login(self.unassigned_staff)
        response = self.client.get(reverse('dashboard_home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard/login/', response.url)

    def test_unassigned_staff_cannot_view_faults(self, mock_assign_sms, mock_sms):
        """2. Verify unassigned non-superuser staff cannot view faults list or detail."""
        self.client.force_login(self.unassigned_staff)
        res_list = self.client.get(reverse('dashboard_faults'))
        self.assertEqual(res_list.status_code, 302)

        res_detail = self.client.get(reverse('dashboard_fault_detail', kwargs={'pk': self.fault_a.id}))
        self.assertEqual(res_detail.status_code, 302)

    def test_unassigned_staff_cannot_view_machines(self, mock_assign_sms, mock_sms):
        """3. Verify unassigned non-superuser staff cannot view machines list."""
        self.client.force_login(self.unassigned_staff)
        response = self.client.get(reverse('dashboard_machines'))
        self.assertEqual(response.status_code, 302)

    def test_unassigned_staff_cannot_edit_machines(self, mock_assign_sms, mock_sms):
        """4. Verify unassigned non-superuser staff cannot create or edit machines."""
        self.client.force_login(self.unassigned_staff)
        res_add = self.client.post(reverse('dashboard_machine_add'), {'name': 'Illegal Machine 99', 'status': 'OPERATIONAL'})
        self.assertEqual(res_add.status_code, 302)
        self.assertFalse(Machine.objects.filter(name='Illegal Machine 99').exists())

        res_edit = self.client.post(reverse('dashboard_machine_edit', kwargs={'pk': self.machine_a.id}), {'name': 'Hacked Name', 'status': 'OFFLINE'})
        self.assertEqual(res_edit.status_code, 302)
        self.machine_a.refresh_from_db()
        self.assertNotEqual(self.machine_a.name, 'Hacked Name')

    def test_unassigned_technician_cannot_be_assigned_to_factory_fault(self, mock_assign_sms, mock_sms):
        """5. Verify an unassigned technician (factory=None) cannot be assigned to a factory fault."""
        with self.assertRaises(ValidationError) as ctx:
            assign_fault_to_technician(self.fault_open_a.id, self.tech_user_unassigned)
        self.assertIn("does not belong to factory", str(ctx.exception))

    def test_technician_from_another_factory_cannot_be_assigned(self, mock_assign_sms, mock_sms):
        """6. Verify a technician from Factory B cannot be assigned to Factory A's fault."""
        with self.assertRaises(ValidationError) as ctx:
            assign_fault_to_technician(self.fault_open_a.id, self.tech_user_b)
        self.assertIn("does not belong to factory", str(ctx.exception))

    def test_same_factory_technician_can_be_assigned(self, mock_assign_sms, mock_sms):
        """7. Verify a technician from Factory A can be successfully assigned to Factory A's fault."""
        fault = assign_fault_to_technician(self.fault_open_a.id, self.tech_user_a)
        self.assertEqual(fault.assigned_to, self.tech_user_a)
        self.assertEqual(fault.status, FaultReport.STATUS_ASSIGNED)

    def test_superuser_retains_global_access(self, mock_assign_sms, mock_sms):
        """8. Verify superusers retain global access across all dashboard views."""
        self.client.force_login(self.superuser)

        res_home = self.client.get(reverse('dashboard_home'))
        self.assertEqual(res_home.status_code, 200)

        res_faults = self.client.get(reverse('dashboard_faults'))
        self.assertEqual(res_faults.status_code, 200)

        res_detail = self.client.get(reverse('dashboard_fault_detail', kwargs={'pk': self.fault_b.id}))
        self.assertEqual(res_detail.status_code, 200)

        res_machines = self.client.get(reverse('dashboard_machines'))
        self.assertEqual(res_machines.status_code, 200)

    def test_unauthorized_technician_sms_sender(self, mock_assign_sms, mock_sms):
        """Verify that SMS commands from an unregistered phone number are rejected."""
        res = process_incoming_technician_sms('+2349999999999', f'ACCEPT {self.fault_a.id}')
        self.assertEqual(res['status'], 'error')
        self.assertEqual(res['reason'], 'technician_not_found')

    def test_technician_modify_other_technician_fault(self, mock_assign_sms, mock_sms):
        """Verify that a technician cannot modify a fault assigned to another technician."""
        res = process_incoming_technician_sms(self.tech_a.phone_number, f'ACCEPT {self.fault_b.id}')
        self.assertEqual(res['status'], 'error')
        self.assertEqual(res['reason'], 'unauthorized_fault')

    def test_factory_users_cannot_access_another_factory_records(self, mock_assign_sms, mock_sms):
        """Verify server-side isolation: Supervisor from Factory A cannot view Factory B's records."""
        self.client.force_login(self.sup_user_a)
        response_fault = self.client.get(reverse('dashboard_fault_detail', kwargs={'pk': self.fault_b.id}))
        self.assertEqual(response_fault.status_code, 404)

        response_machine = self.client.get(reverse('dashboard_machine_edit', kwargs={'pk': self.machine_b.id}))
        self.assertEqual(response_machine.status_code, 404)

    def test_valid_technician_workflow_still_works(self, mock_assign_sms, mock_sms):
        """9. Verify that the full technician workflow (ACCEPT -> START -> RESOLVE) operates cleanly."""
        res_accept = process_incoming_technician_sms(self.tech_a.phone_number, f'ACCEPT {self.fault_a.id}')
        self.assertEqual(res_accept['status'], 'success')
        self.fault_a.refresh_from_db()
        self.assertEqual(self.fault_a.status, FaultReport.STATUS_ACCEPTED)

        res_start = process_incoming_technician_sms(self.tech_a.phone_number, f'START {self.fault_a.id}')
        self.assertEqual(res_start['status'], 'success')
        self.fault_a.refresh_from_db()
        self.assertEqual(self.fault_a.status, FaultReport.STATUS_IN_PROGRESS)

        res_resolve = process_incoming_technician_sms(self.tech_a.phone_number, f'RESOLVE {self.fault_a.id}')
        self.assertEqual(res_resolve['status'], 'success')
        self.fault_a.refresh_from_db()
        self.assertEqual(self.fault_a.status, FaultReport.STATUS_RESOLVED)
