"""
Tests for the FactoryPulse Supervisor Dashboard and Machine Management.
"""

from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from ussd.models import FaultReport, Machine, Technician
from ussd.services import update_fault_status, get_dashboard_stats, assign_fault_to_technician, get_available_technicians


User = get_user_model()


class DashboardAuthTests(TestCase):
    """
    Tests ensuring appropriate authentication and authorization restrictions for the dashboard.
    """

    def setUp(self):
        self.client = Client()
        self.home_url = reverse('dashboard_home')
        self.faults_url = reverse('dashboard_faults')
        self.machines_url = reverse('dashboard_machines')

        # Create test users
        self.staff_user = User.objects.create_user(
            username='staff', password='password123', is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username='regular', password='password123', is_staff=False
        )

    def test_anonymous_user_redirected_to_custom_login(self):
        """Unauthenticated users must be redirected to the custom dashboard login page."""
        for url in [self.home_url, self.faults_url, self.machines_url]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse('dashboard_login'), response.url)

    def test_regular_user_redirected_to_custom_login(self):
        """Authenticated but non-staff users must not access the dashboard."""
        self.client.login(username='regular', password='password123')
        for url in [self.home_url, self.faults_url, self.machines_url]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse('dashboard_login'), response.url)

    def test_staff_user_can_access_dashboard(self):
        """Staff users are allowed to access the dashboard views."""
        self.client.login(username='staff', password='password123')
        for url in [self.home_url, self.faults_url, self.machines_url]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_login_page_renders(self):
        """Custom login page renders successfully."""
        response = self.client.get(reverse('dashboard_login'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('Supervisor Dashboard Login', response.content.decode('utf-8'))

    def test_login_successful_for_staff(self):
        """Staff user can log in via custom login page."""
        response = self.client.post(reverse('dashboard_login'), {
            'username': 'staff',
            'password': 'password123',
            'next': reverse('dashboard_home'),
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard_home'))

    def test_login_fails_for_non_staff(self):
        """Non-staff user login attempt shows unauthorized error."""
        response = self.client.post(reverse('dashboard_login'), {
            'username': 'regular',
            'password': 'password123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Only authorized staff accounts', response.content.decode('utf-8'))

    def test_login_fails_for_invalid_credentials(self):
        """Invalid credentials show error message."""
        response = self.client.post(reverse('dashboard_login'), {
            'username': 'staff',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Invalid username or password', response.content.decode('utf-8'))

    def test_logout_view(self):
        """Logging out clears session and redirects to custom login page."""
        self.client.login(username='staff', password='password123')
        response = self.client.get(reverse('dashboard_logout'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard_login'))



class DashboardFeaturesTests(TestCase):
    """
    Tests for dashboard listings, calculations, and filtering features.
    """

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='staff', password='password123', is_staff=True
        )
        self.client.login(username='staff', password='password123')

        # Clear any auto-seeded machines to start with a clean slate
        Machine.objects.all().delete()

        # Seed machines
        self.gen = Machine.objects.create(name='Generator', status='OPERATIONAL')
        self.mill = Machine.objects.create(name='Milling Machine', status='MAINTENANCE')

        # Seed fault reports
        self.f1 = FaultReport.objects.create(
            machine='Generator', problem='Overheating', severity='High', status='OPEN'
        )
        self.f2 = FaultReport.objects.create(
            machine='Milling Machine', problem='Not working', severity='Critical', status='ASSIGNED'
        )
        self.f3 = FaultReport.objects.create(
            machine='Generator', problem='Making noise', severity='Low', status='RESOLVED'
        )

    def test_dashboard_stats_calculations(self):
        """Dashboard home must correctly calculate and display stats."""
        stats = get_dashboard_stats()
        self.assertEqual(stats['total_faults'], 3)
        self.assertEqual(stats['open_faults'], 1)
        self.assertEqual(stats['critical_faults'], 1)
        self.assertEqual(stats['resolved_faults'], 1)
        self.assertEqual(stats['severity_counts']['High'], 1)
        self.assertEqual(stats['status_counts']['ASSIGNED'], 1)

        # Verify home page renders stats
        response = self.client.get(reverse('dashboard_home'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('3', content)  # Total Faults count
        self.assertIn('1', content)  # Open / Critical / Resolved count

    def test_faults_list_and_details_views(self):
        """Faults list and detail pages must render correctly."""
        # List view
        response = self.client.get(reverse('dashboard_faults'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('Generator', content)
        self.assertIn('Milling Machine', content)

        # Detail view
        response = self.client.get(reverse('dashboard_fault_detail', args=[self.f1.id]))
        self.assertEqual(response.status_code, 200)
        detail_content = response.content.decode('utf-8')
        self.assertIn('Overheating', detail_content)
        self.assertIn('High', detail_content)

    def test_faults_filtering_and_search(self):
        """Dashboard faults page must support search queries and status/severity filters."""
        # Filter by status = RESOLVED
        response = self.client.get(reverse('dashboard_faults') + '?status=RESOLVED')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('Making noise', content)
        self.assertNotIn('Overheating', content)

        # Filter by severity = Critical
        response = self.client.get(reverse('dashboard_faults') + '?severity=Critical')
        content = response.content.decode('utf-8')
        self.assertIn('Not working', content)
        self.assertNotIn('Making noise', content)

        # Search query matching problem name
        response = self.client.get(reverse('dashboard_faults') + '?q=Overheating')
        content = response.content.decode('utf-8')
        self.assertIn('Overheating', content)
        self.assertNotIn('Not working', content)


class FaultWorkflowTests(TestCase):
    """
    Tests checking state machine workflows and transitions.
    """

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='staff', password='password123', is_staff=True
        )
        self.client.login(username='staff', password='password123')

        self.fault = FaultReport.objects.create(
            machine='Generator', problem='Not working', severity='High', status='OPEN'
        )

    def test_valid_status_transitions(self):
        """Ensure valid forward transitions work correctly."""
        # OPEN -> ASSIGNED
        fault = update_fault_status(self.fault.id, 'ASSIGNED')
        self.assertEqual(fault.status, 'ASSIGNED')

        # ASSIGNED -> IN_PROGRESS
        fault = update_fault_status(fault.id, 'IN_PROGRESS')
        self.assertEqual(fault.status, 'IN_PROGRESS')

        # IN_PROGRESS -> RESOLVED
        fault = update_fault_status(fault.id, 'RESOLVED')
        self.assertEqual(fault.status, 'RESOLVED')

    def test_reopen_transitions(self):
        """Ensure reverting back to OPEN from other non-resolved states works."""
        # OPEN -> ASSIGNED -> OPEN
        update_fault_status(self.fault.id, 'ASSIGNED')
        fault = update_fault_status(self.fault.id, 'OPEN')
        self.assertEqual(fault.status, 'OPEN')

        # OPEN -> ASSIGNED -> IN_PROGRESS -> OPEN
        update_fault_status(self.fault.id, 'ASSIGNED')
        update_fault_status(self.fault.id, 'IN_PROGRESS')
        fault = update_fault_status(self.fault.id, 'OPEN')
        self.assertEqual(fault.status, 'OPEN')

    def test_invalid_transitions_are_blocked(self):
        """Illegal status workflow transitions must be blocked."""
        # OPEN -> RESOLVED (direct) is invalid
        with self.assertRaises(ValidationError):
            update_fault_status(self.fault.id, 'RESOLVED')

        # Transitioning out of RESOLVED is completely blocked
        update_fault_status(self.fault.id, 'ASSIGNED')
        update_fault_status(self.fault.id, 'IN_PROGRESS')
        update_fault_status(self.fault.id, 'RESOLVED')

        with self.assertRaises(ValidationError):
            update_fault_status(self.fault.id, 'OPEN')

    def test_view_post_updates_status(self):
        """POST request to details view updates status if transition is valid."""
        url = reverse('dashboard_fault_detail', args=[self.fault.id])
        
        # POST to ASSIGNED
        response = self.client.post(url, {'status': 'ASSIGNED'})
        self.assertEqual(response.status_code, 302)  # Redirect on success
        
        self.fault.refresh_from_db()
        self.assertEqual(self.fault.status, 'ASSIGNED')


class MachineManagementTests(TestCase):
    """
    Tests verifying Machine CRUD and listing in the dashboard.
    """

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='staff', password='password123', is_staff=True
        )
        self.client.login(username='staff', password='password123')
        
        # Clear auto-seeded machines to avoid conflicts
        Machine.objects.all().delete()

    def test_machine_list_displays_machines(self):
        """Machine list page must display all active machines with statuses."""
        m1 = Machine.objects.create(name='Generator', status='OPERATIONAL')
        m2 = Machine.objects.create(name='Packaging Machine', status='MAINTENANCE')

        response = self.client.get(reverse('dashboard_machines'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('Generator', content)
        self.assertIn('Packaging Machine', content)

    def test_machine_creation(self):
        """Supervisors can successfully register a new machine."""
        url = reverse('dashboard_machine_add')
        
        # Valid POST
        response = self.client.post(url, {
            'name': 'Milling Machine',
            'status': 'OPERATIONAL'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Machine.objects.filter(name='Milling Machine').exists())

    def test_machine_creation_validation(self):
        """Supervisors cannot register a machine with a duplicate name."""
        Machine.objects.create(name='Generator', status='OPERATIONAL')
        url = reverse('dashboard_machine_add')

        # Duplicate POST
        response = self.client.post(url, {
            'name': 'Generator',
            'status': 'OFFLINE'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('already exists', response.content.decode('utf-8'))


@patch('ussd.sms_service.send_technician_assignment_sms')
class TechnicianAssignmentTests(TestCase):
    """
    Tests for Technician creation, fault assignment workflow, validations, and dashboard integration.
    SMS notifications are mocked at the class level so no real AT API calls are made.
    """

    def setUp(self, mock_sms=None):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='staff_sup', password='password123', is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username='regular_worker', password='password123', is_staff=False
        )

        # Clear auto-seeded data for a deterministic test state
        Machine.objects.all().delete()
        Technician.objects.all().delete()

        # Create technician user & profile
        self.tech_user_1 = User.objects.create_user(
            username='musa_tech', password='password123', first_name='Musa', last_name='Ibrahim'
        )
        self.tech_profile_1 = Technician.objects.create(
            user=self.tech_user_1,
            name='Musa Ibrahim',
            phone_number='+2348011112222'
        )

        self.tech_user_2 = User.objects.create_user(
            username='abdullahi_tech', password='password123', first_name='Abdullahi', last_name='Yusuf'
        )
        self.tech_profile_2 = Technician.objects.create(
            user=self.tech_user_2,
            name='Abdullahi Yusuf',
            phone_number='+2348033334444'
        )

        # Create faults
        self.fault_open = FaultReport.objects.create(
            machine='Generator',
            problem='Overheating',
            severity='High',
            status=FaultReport.STATUS_OPEN
        )

        self.fault_resolved = FaultReport.objects.create(
            machine='Packaging Machine',
            problem='Broken belt',
            severity='Medium',
            status=FaultReport.STATUS_RESOLVED
        )

    def test_technician_model_structure(self, mock_sms):
        """Technicians are properly associated with User and store name and phone."""
        self.assertEqual(self.tech_profile_1.name, 'Musa Ibrahim')
        self.assertEqual(self.tech_profile_1.phone_number, '+2348011112222')
        self.assertEqual(self.tech_user_1.technician_profile, self.tech_profile_1)
        self.assertIn('Musa Ibrahim', str(self.tech_profile_1))

    def test_assign_fault_service_success(self, mock_sms):
        """assign_fault_to_technician service assigns technician and updates status to ASSIGNED."""
        fault = assign_fault_to_technician(
            fault_id=self.fault_open.id,
            technician_user_or_id=self.tech_user_1,
            notes='Check cooling fan'
        )
        self.assertEqual(fault.status, FaultReport.STATUS_ASSIGNED)
        self.assertEqual(fault.assigned_to, self.tech_user_1)
        self.assertEqual(fault.assignment_notes, 'Check cooling fan')

    def test_cannot_assign_non_technician_user(self, mock_sms):
        """Users without a technician_profile cannot be assigned."""
        with self.assertRaises(ValidationError):
            assign_fault_to_technician(
                fault_id=self.fault_open.id,
                technician_user_or_id=self.regular_user
            )

    def test_cannot_assign_resolved_fault(self, mock_sms):
        """Resolved faults cannot be assigned."""
        with self.assertRaises(ValidationError):
            assign_fault_to_technician(
                fault_id=self.fault_resolved.id,
                technician_user_or_id=self.tech_user_1
            )

    def test_supervisor_can_assign_via_dashboard_view(self, mock_sms):
        """Supervisor can submit assignment form via POST to dashboard fault detail."""
        self.client.login(username='staff_sup', password='password123')
        url = reverse('dashboard_fault_detail', args=[self.fault_open.id])

        response = self.client.post(url, {
            'action': 'assign',
            'technician_id': str(self.tech_user_1.id),
            'notes': 'Urgent repair required'
        })
        self.assertEqual(response.status_code, 302)

        self.fault_open.refresh_from_db()
        self.assertEqual(self.fault_open.status, FaultReport.STATUS_ASSIGNED)
        self.assertEqual(self.fault_open.assigned_to, self.tech_user_1)
        self.assertEqual(self.fault_open.assignment_notes, 'Urgent repair required')

    def test_unauthorized_user_cannot_assign_fault(self, mock_sms):
        """Anonymous or non-staff users cannot post assignments."""
        url = reverse('dashboard_fault_detail', args=[self.fault_open.id])
        response = self.client.post(url, {
            'action': 'assign',
            'technician_id': str(self.tech_user_1.id)
        })
        # Redirected to login
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('dashboard_login'), response.url)

        self.fault_open.refresh_from_db()
        self.assertEqual(self.fault_open.status, FaultReport.STATUS_OPEN)
        self.assertIsNone(self.fault_open.assigned_to)

    def test_full_workflow_progression(self, mock_sms):
        """Complete workflow progression from OPEN -> ASSIGNED -> IN_PROGRESS -> RESOLVED."""
        self.client.login(username='staff_sup', password='password123')
        url = reverse('dashboard_fault_detail', args=[self.fault_open.id])

        # 1. Assign
        self.client.post(url, {'action': 'assign', 'technician_id': str(self.tech_user_1.id)})
        self.fault_open.refresh_from_db()
        self.assertEqual(self.fault_open.status, 'ASSIGNED')

        # 2. Start work
        self.client.post(url, {'status': 'IN_PROGRESS'})
        self.fault_open.refresh_from_db()
        self.assertEqual(self.fault_open.status, 'IN_PROGRESS')

        # 3. Mark resolved
        self.client.post(url, {'status': 'RESOLVED'})
        self.fault_open.refresh_from_db()
        self.assertEqual(self.fault_open.status, 'RESOLVED')

    def test_dashboard_displays_assigned_technician(self, mock_sms):
        """Faults list and detail view render the assigned technician's name."""
        self.client.login(username='staff_sup', password='password123')
        assign_fault_to_technician(self.fault_open.id, self.tech_user_1)

        # Faults list view
        response = self.client.get(reverse('dashboard_faults'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('Musa Ibrahim', response.content.decode('utf-8'))

        # Fault detail view
        detail_response = self.client.get(reverse('dashboard_fault_detail', args=[self.fault_open.id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertIn('Musa Ibrahim', detail_response.content.decode('utf-8'))

    def test_dashboard_filtering_by_assigned_technician(self, mock_sms):
        """Supervisor can filter faults list by assigned technician."""
        self.client.login(username='staff_sup', password='password123')
        
        # Assign fault_open to Musa
        assign_fault_to_technician(self.fault_open.id, self.tech_user_1)

        # Create another fault assigned to Abdullahi
        fault_abdullahi = FaultReport.objects.create(
            machine='Milling Machine',
            problem='Making noise',
            severity='Low',
            status=FaultReport.STATUS_OPEN
        )
        assign_fault_to_technician(fault_abdullahi.id, self.tech_user_2)

        # Filter by Musa
        res_musa = self.client.get(reverse('dashboard_faults') + f'?assigned_to={self.tech_user_1.id}')
        content_musa = res_musa.content.decode('utf-8')
        self.assertIn('Overheating', content_musa)
        self.assertNotIn('Making noise', content_musa)

        # Filter by Abdullahi
        res_abd = self.client.get(reverse('dashboard_faults') + f'?assigned_to={self.tech_user_2.id}')
        content_abd = res_abd.content.decode('utf-8')
        self.assertIn('Making noise', content_abd)
        self.assertNotIn('Overheating', content_abd)

