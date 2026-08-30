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
