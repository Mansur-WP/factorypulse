from django.apps import AppConfig
from django.db.models.signals import post_migrate


class UssdConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ussd'

    def ready(self):
        post_migrate.connect(seed_default_data, sender=self)


def seed_default_data(sender, **kwargs):
    try:
        from .models import Machine, Technician
        from django.contrib.auth import get_user_model
        
        # 1. Seed default machines
        default_machines = ['Generator', 'Packaging Machine', 'Milling Machine']
        for name in default_machines:
            Machine.objects.get_or_create(name=name)

        # 2. Seed default technicians
        User = get_user_model()
        sample_technicians = [
            {'username': 'musa', 'name': 'Musa Ibrahim', 'phone': '+2348011112222'},
            {'username': 'abdullahi', 'name': 'Abdullahi Yusuf', 'phone': '+2348033334444'},
            {'username': 'sani', 'name': 'Sani Bello', 'phone': '+2348055556666'},
        ]
        for tech_info in sample_technicians:
            user, _ = User.objects.get_or_create(
                username=tech_info['username'],
                defaults={'first_name': tech_info['name'].split()[0], 'last_name': tech_info['name'].split()[-1]}
            )
            Technician.objects.get_or_create(
                user=user,
                defaults={'name': tech_info['name'], 'phone_number': tech_info['phone']}
            )
    except Exception:
        # Ignore errors if DB is not ready yet
        pass
