from django.contrib import admin
from .models import FaultReport, Machine, Technician


@admin.register(FaultReport)
class FaultReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'machine', 'severity', 'status', 'assigned_to', 'phone_number', 'created_at')
    list_filter = ('status', 'severity', 'machine', 'assigned_to')
    search_fields = ('machine', 'problem', 'phone_number')


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name',)


@admin.register(Technician)
class TechnicianAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'user', 'phone_number', 'created_at')
    search_fields = ('name', 'phone_number', 'user__username')
