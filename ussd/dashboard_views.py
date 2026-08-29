"""
FactoryPulse Supervisor Dashboard Views

All dashboard views are protected with Django staff authentication.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.contrib import messages
from django.core.exceptions import ValidationError

from .models import FaultReport, Machine
from .services import (
    update_fault_status,
    get_dashboard_stats,
    get_recent_activity,
)


@staff_member_required
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


@staff_member_required
def dashboard_faults(request):
    """
    Displays all reported machine faults with simple search and status/severity filters.
    """
    q_search = request.GET.get('q', '').strip()
    current_severity = request.GET.get('severity', '').strip()
    current_status = request.GET.get('status', '').strip()

    faults = FaultReport.objects.all()

    if q_search:
        faults = faults.filter(
            Q(machine__icontains=q_search) |
            Q(problem__icontains=q_search) |
            Q(phone_number__icontains=q_search) |
            Q(telegram_username__icontains=q_search)
        )

    if current_severity:
        faults = faults.filter(severity=current_severity)

    if current_status:
        faults = faults.filter(status=current_status)

    context = {
        'faults': faults,
        'q_search': q_search,
        'current_severity': current_severity,
        'current_status': current_status,
    }
    return render(request, 'ussd/dashboard_faults.html', context)


@staff_member_required
def dashboard_fault_detail(request, pk):
    """
    Displays the full details of a specific fault report and handles status updates.
    """
    fault = get_object_or_404(FaultReport, pk=pk)

    if request.method == 'POST':
        new_status = request.POST.get('status', '').strip()
        try:
            update_fault_status(fault.id, new_status)
            messages.success(request, f"Fault status updated to {new_status} successfully.")
            return redirect('dashboard_fault_detail', pk=fault.id)
        except ValidationError as e:
            messages.error(request, e.message)
            return redirect('dashboard_fault_detail', pk=fault.id)

    context = {
        'fault': fault,
    }
    return render(request, 'ussd/dashboard_fault_detail.html', context)


@staff_member_required
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


@staff_member_required
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


@staff_member_required
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
