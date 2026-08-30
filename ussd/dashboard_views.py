"""
FactoryPulse Supervisor Dashboard Views

All dashboard views are protected with Django staff authentication
using a dedicated login page.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Q
from django.contrib import messages
from django.core.exceptions import ValidationError

from .models import FaultReport, Machine, Technician
from .services import (
    update_fault_status,
    get_dashboard_stats,
    get_recent_activity,
    get_available_technicians,
    assign_fault_to_technician,
)


def _get_safe_next_url(request, fallback='dashboard_home') -> str:
    """
    Sanitizes the redirect URL to prevent Open Redirect vulnerabilities.
    Only allows relative paths or URLs matching the current request's host.
    """
    next_url = request.POST.get('next') or request.GET.get('next') or ''
    next_url = next_url.strip()
    if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}):
        return next_url
    return fallback


def supervisor_required(view_func):
    """
    Decorator for views that checks if the user is logged in and is a staff member,
    redirecting to the custom dashboard login page if not.
    """
    decorator = user_passes_test(
        lambda u: u.is_authenticated and u.is_active and u.is_staff,
        login_url='dashboard_login'
    )
    return decorator(view_func)


def dashboard_login(request):
    """
    Custom login view for supervisors and staff members.
    Safely validates next redirect parameter to prevent open redirect vulnerabilities.
    """
    if request.user.is_authenticated and request.user.is_staff:
        safe_next = _get_safe_next_url(request)
        return redirect(safe_next)

    error_message = None
    form_data = {}

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        safe_next = _get_safe_next_url(request)
        form_data = {'username': username}

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_staff:
                login(request, user)
                return redirect(safe_next)
            else:
                error_message = "Access denied. Only authorized staff accounts can access the Supervisor Dashboard."
        else:
            error_message = "Invalid username or password. Please try again."

    context = {
        'error_message': error_message,
        'form_data': form_data,
        'next_url': _get_safe_next_url(request, fallback=''),
    }
    return render(request, 'ussd/dashboard_login.html', context)


@require_POST
def dashboard_logout(request):
    """
    Logs out the supervisor and redirects to the dashboard login page.
    Requires POST to protect against CSRF logout attacks.
    """
    logout(request)
    return redirect('dashboard_login')


def _get_supervisor_factory(user):
    """
    Returns the Factory instance associated with a supervisor user, if any.
    Superusers or unassigned staff return None (global platform view).
    """
    if not user or not user.is_authenticated or user.is_superuser:
        return None
    if hasattr(user, 'supervisor_profile') and user.supervisor_profile and user.supervisor_profile.factory:
        return user.supervisor_profile.factory
    return None


@supervisor_required
def dashboard_home(request):
    """
    Dashboard homepage. Displays statistics summaries, recent reports, and recent activities.
    """
    factory = _get_supervisor_factory(request.user)
    stats = get_dashboard_stats(factory=factory)

    recent_faults = FaultReport.objects.select_related('assigned_to', 'factory')
    if factory:
        recent_faults = recent_faults.filter(factory=factory)
    recent_faults = recent_faults.order_by('-created_at', '-id')[:5]

    recent_activity = get_recent_activity()

    context = {
        'stats': stats,
        'recent_faults': recent_faults,
        'recent_activity': recent_activity,
    }
    return render(request, 'ussd/dashboard_home.html', context)


@supervisor_required
def dashboard_faults(request):
    """
    Displays all reported machine faults with simple search, status/severity filters,
    and assigned technician filtering.
    """
    factory = _get_supervisor_factory(request.user)

    q_search = request.GET.get('q', '').strip()
    current_severity = request.GET.get('severity', '').strip()
    current_status = request.GET.get('status', '').strip()
    current_assigned = request.GET.get('assigned_to', '').strip()

    faults = FaultReport.objects.select_related('assigned_to', 'assigned_to__technician_profile', 'factory').all()
    if factory:
        faults = faults.filter(factory=factory)

    if q_search:
        faults = faults.filter(
            Q(machine__icontains=q_search) |
            Q(problem__icontains=q_search) |
            Q(phone_number__icontains=q_search) |
            Q(telegram_username__icontains=q_search) |
            Q(assigned_to__technician_profile__name__icontains=q_search)
        )

    if current_severity:
        faults = faults.filter(severity=current_severity)

    if current_status:
        faults = faults.filter(status=current_status)

    if current_assigned:
        faults = faults.filter(assigned_to_id=current_assigned)

    technicians = get_available_technicians(factory=factory)

    context = {
        'faults': faults,
        'q_search': q_search,
        'current_severity': current_severity,
        'current_status': current_status,
        'current_assigned': current_assigned,
        'technicians': technicians,
    }
    return render(request, 'ussd/dashboard_faults.html', context)


@supervisor_required
def dashboard_fault_detail(request, pk):
    """
    Displays the full details of a specific fault report and handles status updates & technician assignments.
    """
    factory = _get_supervisor_factory(request.user)
    qs = FaultReport.objects.select_related('assigned_to', 'assigned_to__technician_profile', 'factory').prefetch_related('history')
    if factory:
        qs = qs.filter(factory=factory)

    fault = get_object_or_404(qs, pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action', '').strip()
        
        # Technician assignment action
        if action == 'assign' or 'technician_id' in request.POST:
            tech_id = request.POST.get('technician_id', '').strip()
            notes = request.POST.get('notes', '').strip()
            try:
                from .services import assign_fault_to_technician
                assign_fault_to_technician(fault.id, tech_id, notes)
                fault.refresh_from_db()
                tech_name = fault.assigned_to.technician_profile.name if hasattr(fault.assigned_to, 'technician_profile') else fault.assigned_to.username
                messages.success(request, f"Fault #{fault.id} assigned to {tech_name} successfully.")
                return redirect('dashboard_fault_detail', pk=fault.id)
            except ValidationError as e:
                err_text = e.messages[0] if hasattr(e, 'messages') and e.messages else (e.message if hasattr(e, 'message') else str(e))
                messages.error(request, err_text)
                return redirect('dashboard_fault_detail', pk=fault.id)

        # Status transition action
        new_status = request.POST.get('status', '').strip()
        try:
            update_fault_status(fault.id, new_status)
            messages.success(request, f"Fault status updated to {new_status} successfully.")
            return redirect('dashboard_fault_detail', pk=fault.id)
        except ValidationError as e:
            err_text = e.messages[0] if hasattr(e, 'messages') and e.messages else (e.message if hasattr(e, 'message') else str(e))
            messages.error(request, err_text)
            return redirect('dashboard_fault_detail', pk=fault.id)

    from .services import calculate_fault_downtime
    available_technicians = get_available_technicians(factory=factory)
    timeline = fault.history.all().order_by('timestamp', 'id')
    downtime_info = calculate_fault_downtime(fault)

    context = {
        'fault': fault,
        'available_technicians': available_technicians,
        'timeline': timeline,
        'downtime_info': downtime_info,
    }
    return render(request, 'ussd/dashboard_fault_detail.html', context)


@supervisor_required
def dashboard_machines(request):
    """
    Displays a list of registered machines, their current operational status,
    total faults reported, and the timestamp of their latest fault.
    """
    factory = _get_supervisor_factory(request.user)
    machines = Machine.objects.all()
    if factory:
        machines = machines.filter(factory=factory)

    machines_data = []

    from .services import calculate_fault_downtime, format_duration
    from datetime import timedelta

    for m in machines:
        machine_faults = FaultReport.objects.filter(machine=m.name).prefetch_related('history')
        if factory:
            machine_faults = machine_faults.filter(factory=factory)

        fault_count = machine_faults.count()
        active_fault_count = machine_faults.exclude(status=FaultReport.STATUS_RESOLVED).count()
        last_fault = machine_faults.order_by('-created_at', '-id').first()

        total_sec = sum(calculate_fault_downtime(f)['duration_seconds'] for f in machine_faults)
        downtime_formatted = format_duration(timedelta(seconds=total_sec))

        machines_data.append({
            'id': m.id,
            'name': m.name,
            'status': m.status,
            'status_display': m.get_status_display(),
            'fault_count': fault_count,
            'active_fault_count': active_fault_count,
            'health_status': 'Operational' if active_fault_count == 0 and m.status == 'OPERATIONAL' else 'Attention Required',
            'downtime_formatted': downtime_formatted,
            'last_fault_time': last_fault.created_at if last_fault else None,
        })

    context = {
        'machines_data': machines_data,
    }
    return render(request, 'ussd/dashboard_machines.html', context)


@supervisor_required
def dashboard_machine_add(request):
    """
    Registers a new machine in the system with server-side field length, choice, and factory validation.
    """
    factory = _get_supervisor_factory(request.user)
    form_errors = {}
    form_data = {}

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        status = request.POST.get('status', '').strip()

        valid_statuses = [choice[0] for choice in Machine.STATUS_CHOICES]
        if status not in valid_statuses:
            status = Machine.STATUS_OPERATIONAL

        form_data = {'name': name, 'status': status}

        if not name:
            form_errors['name'] = ['Name field is required.']
        elif len(name) > 100:
            form_errors['name'] = ['Machine name cannot exceed 100 characters.']
        elif Machine.objects.filter(name__iexact=name).exists():
            form_errors['name'] = ['A machine with this name already exists.']

        if not form_errors:
            Machine.objects.create(name=name, status=status, factory=factory)
            messages.success(request, f"Machine '{name}' registered successfully.")
            return redirect('dashboard_machines')

    context = {
        'form_errors': form_errors,
        'form_data': form_data,
    }
    return render(request, 'ussd/dashboard_machine_form.html', context)


@supervisor_required
def dashboard_machine_edit(request, pk):
    """
    Edits the name or operational status of an existing machine with server-side validation.
    """
    factory = _get_supervisor_factory(request.user)
    qs = Machine.objects.all()
    if factory:
        qs = qs.filter(factory=factory)

    machine = get_object_or_404(qs, pk=pk)
    form_errors = {}

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        status = request.POST.get('status', '').strip()

        valid_statuses = [choice[0] for choice in Machine.STATUS_CHOICES]
        if status not in valid_statuses:
            status = machine.status

        if not name:
            form_errors['name'] = ['Name field is required.']
        elif len(name) > 100:
            form_errors['name'] = ['Machine name cannot exceed 100 characters.']
        elif Machine.objects.filter(name__iexact=name).exclude(pk=machine.pk).exists():
            form_errors['name'] = ['A machine with this name already exists.']

        if not form_errors:
            machine.name = name
            machine.status = status
            machine.save()
            messages.success(request, f"Machine '{name}' updated successfully.")
            return redirect('dashboard_machines')

    context = {
        'machine': machine,
        'form_errors': form_errors,
    }
    return render(request, 'ussd/dashboard_machine_form.html', context)
