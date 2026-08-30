from django.contrib import admin
from .models import FaultReport, Machine, Technician, FaultStatusHistory, Factory, SupervisorProfile


@admin.register(Factory)
class FactoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at')
    search_fields = ('name',)


@admin.register(SupervisorProfile)
class SupervisorProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'factory', 'created_at')
    list_filter = ('factory',)
    search_fields = ('user__username', 'factory__name')


@admin.register(FaultReport)
class FaultReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'machine', 'factory', 'severity', 'status', 'assigned_to', 'phone_number', 'created_at')
    list_filter = ('factory', 'status', 'severity', 'machine', 'assigned_to')
    search_fields = ('machine', 'problem', 'phone_number')


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'factory', 'status', 'created_at')
    list_filter = ('factory', 'status')
    search_fields = ('name',)


@admin.register(Technician)
class TechnicianAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'factory', 'user', 'phone_number', 'created_at')
    list_filter = ('factory',)
    search_fields = ('name', 'phone_number', 'user__username')


@admin.register(FaultStatusHistory)
class FaultStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'fault', 'status', 'actor_name', 'timestamp')
    list_filter = ('status', 'timestamp')
    search_fields = ('fault__id', 'actor_name', 'notes')

