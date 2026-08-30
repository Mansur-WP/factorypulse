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
        user = User.objects.create_user(username='staff', password='pass', is_staff=True)
        self.client.force_login(user)

        response = self.client.post(reverse('dashboard_machine_add'), {
            'name': 'New Testing Machine',
            'status': 'INVALID_HACKED_STATUS'
        })
        self.assertEqual(response.status_code, 302)
        machine = Machine.objects.get(name='New Testing Machine')
        self.assertEqual(machine.status, Machine.STATUS_OPERATIONAL)


from ussd.models import Factory, SupervisorProfile, FaultStatusHistory

class Phase3AccessControlTests(TestCase):
    """Focused unit tests for Phase 3 role-based access control and factory isolation."""

    def setUp(self):
        self.client = Client()
        self.factory_a = Factory.objects.create(name="Factory Alpha")
        self.factory_b = Factory.objects.create(name="Factory Beta")

        # Factory A Supervisor
        self.sup_user_a = User.objects.create_user(username='sup_alpha', password='password123', is_staff=True)
        SupervisorProfile.objects.create(user=self.sup_user_a, factory=self.factory_a)

        # Factory B Supervisor
        self.sup_user_b = User.objects.create_user(username='sup_beta', password='password123', is_staff=True)
        SupervisorProfile.objects.create(user=self.sup_user_b, factory=self.factory_b)

        # Technician A (Factory A)
        self.tech_user_a = User.objects.create_user(username='tech_alpha', password='password123', is_staff=False)
        self.tech_a = Technician.objects.create(user=self.tech_user_a, name='Tech Alpha', phone_number='+2348111111111', factory=self.factory_a)

        # Technician B (Factory B)
        self.tech_user_b = User.objects.create_user(username='tech_beta', password='password123', is_staff=False)
        self.tech_b = Technician.objects.create(user=self.tech_user_b, name='Tech Beta', phone_number='+2348222222222', factory=self.factory_b)

        # Faults
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

    def test_unauthorized_technician_sms_sender(self):
        """Verify that SMS commands from an unregistered phone number are rejected."""
        res = process_incoming_technician_sms('+2349999999999', f'ACCEPT {self.fault_a.id}')
        self.assertEqual(res['status'], 'error')
        self.assertEqual(res['reason'], 'technician_not_found')

    def test_technician_modify_other_technician_fault(self):
        """Verify that a technician cannot modify a fault assigned to another technician."""
        # Tech A trying to resolve Tech B's fault
        res = process_incoming_technician_sms(self.tech_a.phone_number, f'ACCEPT {self.fault_b.id}')
        self.assertEqual(res['status'], 'error')
        self.assertEqual(res['reason'], 'unauthorized_fault')

    def test_worker_cannot_access_supervisor_dashboard(self):
        """Verify that a non-staff worker/user cannot access the supervisor dashboard."""
        worker_user = User.objects.create_user(username='worker1', password='password123', is_staff=False)
        self.client.force_login(worker_user)

        response = self.client.get(reverse('dashboard_home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard/login/', response.url)

    def test_technician_cannot_access_supervisor_actions(self):
        """Verify that a technician (is_staff=False) cannot execute supervisor-only actions."""
        self.client.force_login(self.tech_user_a)

        # Attempt to add a machine
        response = self.client.post(reverse('dashboard_machine_add'), {'name': 'Illegal Machine', 'status': 'OPERATIONAL'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard/login/', response.url)
        self.assertFalse(Machine.objects.filter(name='Illegal Machine').exists())

    def test_factory_users_cannot_access_another_factory_records(self):
        """Verify server-side isolation: Supervisor from Factory A cannot view or edit Factory B's fault or machine."""
        self.client.force_login(self.sup_user_a)

        # Attempting to access Factory B's fault detail -> HTTP 404
        response_fault = self.client.get(reverse('dashboard_fault_detail', kwargs={'pk': self.fault_b.id}))
        self.assertEqual(response_fault.status_code, 404)

        # Attempting to edit Factory B's machine -> HTTP 404
        machine_b = Machine.objects.create(name="Beta Generator", status="OPERATIONAL", factory=self.factory_b)
        response_machine = self.client.get(reverse('dashboard_machine_edit', kwargs={'pk': machine_b.id}))
        self.assertEqual(response_machine.status_code, 404)

    def test_valid_technician_workflow_still_works(self):
        """Verify that the full technician workflow (ACCEPT -> START -> RESOLVE) operates cleanly."""
        # 1. ACCEPT
        res_accept = process_incoming_technician_sms(self.tech_a.phone_number, f'ACCEPT {self.fault_a.id}')
        self.assertEqual(res_accept['status'], 'success')
        self.fault_a.refresh_from_db()
        self.assertEqual(self.fault_a.status, FaultReport.STATUS_ACCEPTED)

        # 2. START
        res_start = process_incoming_technician_sms(self.tech_a.phone_number, f'START {self.fault_a.id}')
        self.assertEqual(res_start['status'], 'success')
        self.fault_a.refresh_from_db()
        self.assertEqual(self.fault_a.status, FaultReport.STATUS_IN_PROGRESS)

        # 3. RESOLVE
        res_resolve = process_incoming_technician_sms(self.tech_a.phone_number, f'RESOLVE {self.fault_a.id}')
        self.assertEqual(res_resolve['status'], 'success')
        self.fault_a.refresh_from_db()
        self.assertEqual(self.fault_a.status, FaultReport.STATUS_RESOLVED)
