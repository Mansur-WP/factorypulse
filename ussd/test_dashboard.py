"""
Tests for the FactoryPulse Supervisor Dashboard and Machine Management.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from ussd.models import FaultReport, Machine
from ussd.services import update_fault_status, get_dashboard_stats

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

    def test_anonymous_user_redirected_to_login(self):
        """Unauthenticated users must be redirected to the login page."""
        for url in [self.home_url, self.faults_url, self.machines_url]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn('login', response.url)

    def test_regular_user_redirected_to_login(self):
        """Authenticated but non-staff users must not access the dashboard."""
        self.client.login(username='regular', password='password123')
        for url in [self.home_url, self.faults_url, self.machines_url]:
            response = self.client.get(url)
            # django's staff_member_required redirects non-staff users to login page
            self.assertEqual(response.status_code, 302)
            self.assertIn('login', response.url)

    def test_staff_user_can_access_dashboard(self):
        """Staff users are allowed to access the dashboard views."""
        self.client.login(username='staff', password='password123')
        for url in [self.home_url, self.faults_url, self.machines_url]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)


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
