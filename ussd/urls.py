from django.urls import path
from .views import ussd_callback, sms_delivery_callback, sms_incoming_callback, landing_page
from . import dashboard_views

urlpatterns = [
    # Public Landing Page
    path('', landing_page, name='landing_page'),

    # USSD callback
    path('ussd/', ussd_callback, name='ussd_callback'),

    # SMS delivery status callback (from Africa's Talking)
    path('sms/delivery/', sms_delivery_callback, name='sms_delivery_callback'),

    # Incoming SMS callback (from Africa's Talking)
    path('sms/incoming/', sms_incoming_callback, name='sms_incoming_callback'),

    # Supervisor Dashboard
    path('dashboard/login/', dashboard_views.dashboard_login, name='dashboard_login'),
    path('dashboard/logout/', dashboard_views.dashboard_logout, name='dashboard_logout'),
    path('dashboard/', dashboard_views.dashboard_home, name='dashboard_home'),
    path('dashboard/faults/', dashboard_views.dashboard_faults, name='dashboard_faults'),
    path('dashboard/faults/<int:pk>/', dashboard_views.dashboard_fault_detail, name='dashboard_fault_detail'),
    path('dashboard/machines/', dashboard_views.dashboard_machines, name='dashboard_machines'),
    path('dashboard/machines/add/', dashboard_views.dashboard_machine_add, name='dashboard_machine_add'),
    path('dashboard/machines/<int:pk>/edit/', dashboard_views.dashboard_machine_edit, name='dashboard_machine_edit'),
]



