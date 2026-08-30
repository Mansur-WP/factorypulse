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
