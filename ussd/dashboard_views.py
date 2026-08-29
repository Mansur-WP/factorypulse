"""
FactoryPulse Supervisor Dashboard Views

All dashboard views are protected with Django staff authentication
using a dedicated login page.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
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
    """
    if request.user.is_authenticated and request.user.is_staff:
        next_url = request.GET.get('next') or request.POST.get('next') or 'dashboard_home'
        return redirect(next_url)

    error_message = None
    form_data = {}

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        next_url = request.POST.get('next', '').strip() or 'dashboard_home'
        form_data = {'username': username}

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_staff:
                login(request, user)
                return redirect(next_url)
            else:
                error_message = "Access denied. Only authorized staff accounts can access the Supervisor Dashboard."
        else:
            error_message = "Invalid username or password. Please try again."

    context = {
        'error_message': error_message,
        'form_data': form_data,
        'next_url': request.GET.get('next', ''),
    }
    return render(request, 'ussd/dashboard_login.html', context)


def dashboard_logout(request):
    """
    Logs out the supervisor and redirects to the dashboard login page.
    """
    logout(request)
    return redirect('dashboard_login')


@supervisor_required
def dashboard_home(request):
    """
    Dashboard homepage. Displays statistics summaries, recent reports, and recent activities.
    """
    stats = get_dashboard_stats()
    recent_faults = FaultReport.objects.order_by('-created_at', '-id')[:5]
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
    q_search = request.GET.get('q', '').strip()
    current_severity = request.GET.get('severity', '').strip()
    current_status = request.GET.get('status', '').strip()
    current_assigned = request.GET.get('assigned_to', '').strip()

    faults = FaultReport.objects.select_related('assigned_to', 'assigned_to__technician_profile').all()

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

    technicians = get_available_technicians()

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
    fault = get_object_or_404(FaultReport.objects.select_related('assigned_to', 'assigned_to__technician_profile'), pk=pk)

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
                messages.error(request, e.message)
                return redirect('dashboard_fault_detail', pk=fault.id)

        # Status transition action
        new_status = request.POST.get('status', '').strip()
        try:
            update_fault_status(fault.id, new_status)
            messages.success(request, f"Fault status updated to {new_status} successfully.")
            return redirect('dashboard_fault_detail', pk=fault.id)
        except ValidationError as e:
            messages.error(request, e.message)
            return redirect('dashboard_fault_detail', pk=fault.id)

    available_technicians = get_available_technicians()

    context = {
        'fault': fault,
        'available_technicians': available_technicians,
    }
    return render(request, 'ussd/dashboard_fault_detail.html', context)



@supervisor_required
def dashboard_machines(request):
    """
    Displays a list of registered machines, their current operational status,
    total faults reported, and the timestamp of their latest fault.
    """
    machines = Machine.objects.all()
    machines_data = []

    for m in machines:
        fault_count = FaultReport.objects.filter(machine=m.name).count()
        last_fault = FaultReport.objects.filter(machine=m.name).order_by('-created_at', '-id').first()
        machines_data.append({
            'id': m.id,
            'name': m.name,
            'status': m.status,
            'status_display': m.get_status_display(),
            'fault_count': fault_count,
            'last_fault_time': last_fault.created_at if last_fault else None,
        })

    context = {
        'machines_data': machines_data,
    }
    return render(request, 'ussd/dashboard_machines.html', context)


@supervisor_required
def dashboard_machine_add(request):
    """
    Registers a new machine in the system.
    """
    form_errors = {}
    form_data = {}

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        status = request.POST.get('status', '').strip()

        form_data = {'name': name, 'status': status}

        if not name:
            form_errors['name'] = ['Name field is required.']
        elif Machine.objects.filter(name__iexact=name).exists():
            form_errors['name'] = ['A machine with this name already exists.']

        if not form_errors:
            Machine.objects.create(name=name, status=status)
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
    Edits the name or operational status of an existing machine.
    """
    machine = get_object_or_404(Machine, pk=pk)
    form_errors = {}

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        status = request.POST.get('status', '').strip()

        if not name:
            form_errors['name'] = ['Name field is required.']
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
