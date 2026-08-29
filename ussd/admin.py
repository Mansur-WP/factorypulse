from django.contrib import admin
from .models import FaultReport, Machine


@admin.register(FaultReport)
class FaultReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'machine', 'severity', 'status', 'phone_number', 'created_at')
    list_filter = ('status', 'severity', 'machine')
    search_fields = ('machine', 'problem', 'phone_number')


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name',)

