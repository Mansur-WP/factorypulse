from django.apps import AppConfig
from django.db.models.signals import post_migrate


class UssdConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ussd'

    def ready(self):
        post_migrate.connect(seed_default_machines, sender=self)


def seed_default_machines(sender, **kwargs):
    try:
        from .models import Machine
        default_machines = ['Generator', 'Packaging Machine', 'Milling Machine']
        for name in default_machines:
            Machine.objects.get_or_create(name=name)
    except Exception:
        # Ignore errors if DB is not ready yet
        pass

