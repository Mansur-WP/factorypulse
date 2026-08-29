from django.db import models
from django.conf import settings


class FaultReport(models.Model):
    STATUS_OPEN = 'OPEN'
    STATUS_ASSIGNED = 'ASSIGNED'
    STATUS_ACCEPTED = 'ACCEPTED'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_RESOLVED = 'RESOLVED'

    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_ASSIGNED, 'Assigned'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_RESOLVED, 'Resolved'),
    ]

    SEVERITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Critical', 'Critical'),
    ]

    phone_number = models.CharField(max_length=20, blank=True, default='')
    telegram_user_id = models.CharField(max_length=50, blank=True, default='', db_index=True)
    telegram_username = models.CharField(max_length=100, blank=True, default='')
    machine = models.CharField(max_length=100)
    problem = models.CharField(max_length=255)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_faults',
    )
    assignment_notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f"Fault #{self.id} - {self.machine} ({self.status})"


class Machine(models.Model):
    STATUS_OPERATIONAL = 'OPERATIONAL'
    STATUS_MAINTENANCE = 'MAINTENANCE'
    STATUS_OFFLINE = 'OFFLINE'

    STATUS_CHOICES = [
        (STATUS_OPERATIONAL, 'Operational'),
        (STATUS_MAINTENANCE, 'Maintenance'),
        (STATUS_OFFLINE, 'Offline'),
    ]

    name = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPERATIONAL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


class Technician(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='technician_profile',
    )
    name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.phone_number})" if self.phone_number else self.name
