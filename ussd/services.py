"""
FactoryPulse Core Business Logic Services

Shared across USSD and Telegram (and future interfaces).
"""

from typing import Optional, List, Dict
from django.db.models import QuerySet
from .models import FaultReport

MACHINES: Dict[str, str] = {
    '1': 'Generator',
    '2': 'Packaging Machine',
    '3': 'Milling Machine',
}

PROBLEMS: Dict[str, str] = {
    '1': 'Not working',
    '2': 'Overheating',
    '3': 'Making noise',
}

SEVERITIES: Dict[str, str] = {
    '1': 'Low',
    '2': 'Medium',
    '3': 'High',
    '4': 'Critical',
}

MACHINE_STATUSES: List[Dict[str, str]] = [
    {'id': '1', 'name': 'Generator', 'status': 'Operational'},
    {'id': '2', 'name': 'Packaging Machine', 'status': 'Operational'},
    {'id': '3', 'name': 'Milling Machine', 'status': 'Operational'},
]


def resolve_machine(input_text: str) -> Optional[str]:
    """
    Resolves machine input from digit ('1'), button label ('1. Generator'), or raw name ('Generator').
    """
    clean = (input_text or '').strip()
    if clean in MACHINES:
        return MACHINES[clean]
    for key, name in MACHINES.items():
        if clean.lower() == name.lower() or clean.lower() == f"{key}. {name}".lower() or clean.lower() == f"{key} {name}".lower():
            return name
    return None


def resolve_problem(input_text: str) -> Optional[str]:
    """
    Resolves predefined problem or 'Other' option.
    Returns problem string or 'OTHER' or None if invalid.
    """
    clean = (input_text or '').strip()
    if clean in PROBLEMS:
        return PROBLEMS[clean]
    if clean == '4' or clean.lower() == '4. other' or clean.lower() == 'other':
        return 'OTHER'
    for key, desc in PROBLEMS.items():
        if clean.lower() == desc.lower() or clean.lower() == f"{key}. {desc}".lower() or clean.lower() == f"{key} {desc}".lower():
            return desc
    return None


def resolve_severity(input_text: str) -> Optional[str]:
    """
    Resolves severity input from digit ('1'), button label ('1. Low'), or raw name ('Low').
    """
    clean = (input_text or '').strip()
    if clean in SEVERITIES:
        return SEVERITIES[clean]
    for key, name in SEVERITIES.items():
        if clean.lower() == name.lower() or clean.lower() == f"{key}. {name}".lower() or clean.lower() == f"{key} {name}".lower():
            return name
    return None


def create_fault_report(
    machine: str,
    problem: str,
    severity: str,
    phone_number: str = '',
    telegram_user_id: str = '',
    telegram_username: str = '',
    status: str = FaultReport.STATUS_OPEN,
) -> FaultReport:
    """
    Creates and persists a FaultReport in the database.
    """
    return FaultReport.objects.create(
        machine=machine,
        problem=problem,
        severity=severity,
        phone_number=phone_number or '',
        telegram_user_id=str(telegram_user_id) if telegram_user_id else '',
        telegram_username=telegram_username or '',
        status=status or FaultReport.STATUS_OPEN,
    )


def get_user_fault_reports(
    telegram_user_id: Optional[str] = None,
    phone_number: Optional[str] = None,
) -> QuerySet[FaultReport]:
    """
    Fetches fault reports strictly isolated to the given Telegram user or phone number.
    """
    if telegram_user_id:
        return FaultReport.objects.filter(telegram_user_id=str(telegram_user_id)).order_by('-id')
    elif phone_number:
        return FaultReport.objects.filter(phone_number=phone_number).order_by('-id')
    return FaultReport.objects.none()


def get_machine_statuses() -> List[Dict[str, str]]:
    """
    Returns the list of factory machines and their operational status from the database.
    """
    from .models import Machine
    try:
        machines = Machine.objects.all()
        if not machines.exists():
            for name in ['Generator', 'Packaging Machine', 'Milling Machine']:
                Machine.objects.get_or_create(name=name)
            machines = Machine.objects.all()
        return [
            {
                'id': str(m.id),
                'name': m.name,
                'status': m.get_status_display(),
            }
            for m in machines
        ]
    except Exception:
        return list(MACHINE_STATUSES)


def update_fault_status(fault_id: int, new_status: str) -> FaultReport:
    """
    Updates the status of a FaultReport, enforcing validation rules.
    Allowed transitions:
      - OPEN -> ASSIGNED
      - ASSIGNED -> IN_PROGRESS
      - IN_PROGRESS -> RESOLVED
      - Any non-RESOLVED state -> OPEN (reopen)
    Raises ValidationError for invalid transitions.
    """
    from django.core.exceptions import ValidationError
    
    try:
        fault = FaultReport.objects.get(pk=fault_id)
    except FaultReport.DoesNotExist:
        raise ValidationError(f"Fault report #{fault_id} does not exist.")

    old_status = fault.status
    if old_status == new_status:
        return fault

    valid = False
    if old_status == FaultReport.STATUS_OPEN:
        if new_status == FaultReport.STATUS_ASSIGNED:
            valid = True
    elif old_status == FaultReport.STATUS_ASSIGNED:
        if new_status in (FaultReport.STATUS_IN_PROGRESS, FaultReport.STATUS_OPEN):
            valid = True
    elif old_status == FaultReport.STATUS_IN_PROGRESS:
        if new_status in (FaultReport.STATUS_RESOLVED, FaultReport.STATUS_OPEN):
            valid = True
    elif old_status == FaultReport.STATUS_RESOLVED:
        # Cannot transition out of resolved
        valid = False

    if not valid:
        raise ValidationError(
            f"Invalid status transition from {old_status} to {new_status}."
        )

    fault.status = new_status
    fault.save()
    return fault


def get_dashboard_stats() -> dict:
    """
    Returns fault statistics for the dashboard.
    """
    total = FaultReport.objects.count()
    open_count = FaultReport.objects.filter(status=FaultReport.STATUS_OPEN).count()
    critical = FaultReport.objects.filter(severity='Critical').count()
    resolved = FaultReport.objects.filter(status=FaultReport.STATUS_RESOLVED).count()

    # Breakdown by severity
    severity_breakdown = {
        'Low': FaultReport.objects.filter(severity='Low').count(),
        'Medium': FaultReport.objects.filter(severity='Medium').count(),
        'High': FaultReport.objects.filter(severity='High').count(),
        'Critical': critical,
    }

    # Breakdown by status
    status_breakdown = {
        'OPEN': open_count,
        'ASSIGNED': FaultReport.objects.filter(status=FaultReport.STATUS_ASSIGNED).count(),
        'IN_PROGRESS': FaultReport.objects.filter(status=FaultReport.STATUS_IN_PROGRESS).count(),
        'RESOLVED': resolved,
    }

    return {
        'total_faults': total,
        'open_faults': open_count,
        'critical_faults': critical,
        'resolved_faults': resolved,
        'severity_counts': severity_breakdown,
        'status_counts': status_breakdown,
    }


def get_recent_activity() -> list:
    """
    Returns recent activities based on FaultReport objects.
    """
    # Fetch 10 most recent fault reports
    recent_reports = FaultReport.objects.order_by('-created_at', '-id')[:10]
    activity = []
    
    for r in recent_reports:
        timestamp = r.created_at
        if r.status == FaultReport.STATUS_RESOLVED:
            activity.append({
                'time': timestamp,
                'message': f"Fault #{r.id} resolved",
                'machine': r.machine,
                'detail': "",
            })
        else:
            activity.append({
                'time': timestamp,
                'message': f"Fault #{r.id} reported",
                'machine': r.machine,
                'detail': f"{r.severity} severity",
            })
            
    return activity

