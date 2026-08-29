from django.db import models


class FaultReport(models.Model):
    STATUS_OPEN = 'OPEN'
    STATUS_ASSIGNED = 'ASSIGNED'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_RESOLVED = 'RESOLVED'

    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_ASSIGNED, 'Assigned'),
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


