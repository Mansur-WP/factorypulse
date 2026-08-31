"""
FactoryPulse Core Business Logic Services

Shared across USSD, Telegram, and Supervisor Dashboard.
"""

from datetime import timedelta
from typing import Optional, List, Dict, Union
from django.db.models import QuerySet, Count
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import FaultReport, Machine, Technician, FaultStatusHistory

User = get_user_model()

# Default seed machines — used only if the Machine table is empty
_DEFAULT_MACHINE_NAMES = ['Generator', 'Packaging Machine', 'Milling Machine']

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


def get_ussd_machine_list() -> Dict[str, str]:
    """
    Returns a numbered dict of machines from the database for USSD menus.
    E.g. {'1': 'Generator', '2': 'Packaging Machine', '3': 'Milling Machine', ...}
    Seeds default machines if the table is empty.
    """
    try:
        machines = Machine.objects.all().order_by('id')
        if not machines.exists():
            for name in _DEFAULT_MACHINE_NAMES:
                Machine.objects.get_or_create(name=name)
            machines = Machine.objects.all().order_by('id')
        return {str(i + 1): m.name for i, m in enumerate(machines)}
    except Exception:
        # Fallback if DB is unreachable
        return {str(i + 1): name for i, name in enumerate(_DEFAULT_MACHINE_NAMES)}


# Backward-compatible alias — modules that import MACHINES get the dynamic list
# Note: This is a function call, not a constant. Importers that need live data
# should call get_ussd_machine_list() directly.
MACHINES = get_ussd_machine_list


def resolve_machine(input_text: str) -> Optional[str]:
    """
    Resolves machine input from digit ('1'), button label ('1. Generator'), or raw name ('Generator').
    Dynamically queries the Machine table.
    """
    machines = get_ussd_machine_list()
    clean = (input_text or '').strip()
    if clean in machines:
        return machines[clean]
    for key, name in machines.items():
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
    Inputs are sanitized and truncated to model max_length boundaries.
    """
    clean_machine = (machine or '').strip()[:100]
    clean_problem = (problem or '').strip()[:255]
    clean_severity = (severity or '').strip()[:20]
    clean_phone = (phone_number or '').strip()[:20]
    clean_tg_id = str(telegram_user_id or '').strip()[:50]
    clean_tg_user = (telegram_username or '').strip()[:100]
    clean_status = (status or FaultReport.STATUS_OPEN).strip()[:20]

    # Look up the machine's factory
    from .models import Machine
    machine_obj = Machine.objects.filter(name__iexact=clean_machine).first()
    factory = machine_obj.factory if machine_obj else None

    fault = FaultReport.objects.create(
        factory=factory,
        machine=clean_machine,
        problem=clean_problem,
        severity=clean_severity,
        phone_number=clean_phone,
        telegram_user_id=clean_tg_id,
        telegram_username=clean_tg_user,
        status=clean_status,
    )

    actor = f"Worker ({clean_phone})" if clean_phone else (f"Telegram (@{clean_tg_user})" if clean_tg_user else "Worker")
    FaultStatusHistory.objects.create(
        fault=fault,
        status=fault.status,
        actor_name=actor,
        notes="Fault reported"
    )
    return fault


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
    try:
        machines = Machine.objects.all()
        if not machines.exists():
            for name in _DEFAULT_MACHINE_NAMES:
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
        return [
            {'id': str(i + 1), 'name': name, 'status': 'Operational'}
            for i, name in enumerate(_DEFAULT_MACHINE_NAMES)
        ]


def get_available_technicians(factory=None) -> QuerySet:
    """
    Returns registered technicians, optionally filtered by factory.
    """
    qs = Technician.objects.select_related('user').all()
    if factory:
        qs = qs.filter(factory=factory)
    return qs


def assign_fault_to_technician(
    fault_id: int,
    technician_user_or_id: Union[User, int, str],
    notes: str = ''
) -> FaultReport:
    """
    Assigns an OPEN fault to a technician, transitioning its status to ASSIGNED.
    Raises ValidationError if the fault is not OPEN/ASSIGNED, is resolved, or user is not a technician.
    """
    try:
        fault = FaultReport.objects.get(pk=fault_id)
    except FaultReport.DoesNotExist:
        raise ValidationError(f"Fault report #{fault_id} does not exist.")

    if fault.status == FaultReport.STATUS_RESOLVED:
        raise ValidationError("Resolved faults cannot be assigned.")

    if fault.status not in (FaultReport.STATUS_OPEN, FaultReport.STATUS_ASSIGNED):
        raise ValidationError(f"Cannot assign a fault in '{fault.get_status_display()}' status.")

    # Resolve technician user
    if isinstance(technician_user_or_id, User):
        tech_user = technician_user_or_id
    else:
        try:
            tech_user = User.objects.get(pk=technician_user_or_id)
        except (User.DoesNotExist, ValueError):
            raise ValidationError("Invalid technician selected.")

    # Verify technician profile exists
    if not hasattr(tech_user, 'technician_profile'):
        raise ValidationError(f"User '{tech_user.username}' is not registered as a technician.")

    # Strict factory match rule:
    # If a fault belongs to a factory, the technician MUST belong to that exact same factory.
    tech_profile = tech_user.technician_profile
    if fault.factory:
        if not tech_profile.factory or tech_profile.factory != fault.factory:
            raise ValidationError(f"Technician '{tech_profile.name}' does not belong to factory '{fault.factory.name}'.")

    fault.assigned_to = tech_user
    if notes:
        fault.assignment_notes = notes.strip()
    fault.status = FaultReport.STATUS_ASSIGNED
    fault.save()

    tech_name = tech_user.technician_profile.name if hasattr(tech_user, 'technician_profile') else (tech_user.get_full_name() or tech_user.username)
    history_notes = f"Assigned to {tech_name}"
    if notes:
        history_notes += f": {notes.strip()}"
    FaultStatusHistory.objects.create(
        fault=fault,
        status=FaultReport.STATUS_ASSIGNED,
        actor_name=tech_name,
        notes=history_notes,
    )

    # Trigger SMS notification — safe, never rolls back the assignment
    try:
        from .sms_service import send_technician_assignment_sms
        tech_profile = getattr(tech_user, 'technician_profile', None)
        send_technician_assignment_sms(fault, tech_profile)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"SMS dispatch failed for fault #{fault.id}: {e}")

    return fault


def update_fault_status(fault_id: int, new_status: str, actor_name: str = '') -> FaultReport:
    """
    Updates the status of a FaultReport, enforcing validation rules and logging history.
    Allowed transitions:
      - OPEN -> ASSIGNED / ACCEPTED
      - ASSIGNED -> ACCEPTED / IN_PROGRESS / OPEN
      - ACCEPTED -> IN_PROGRESS / OPEN
      - IN_PROGRESS -> RESOLVED / OPEN
    Raises ValidationError for invalid transitions.
    """
    try:
        fault = FaultReport.objects.get(pk=fault_id)
    except FaultReport.DoesNotExist:
        raise ValidationError(f"Fault report #{fault_id} does not exist.")

    old_status = fault.status
    if old_status == new_status:
        return fault

    valid = False
    if old_status == FaultReport.STATUS_OPEN:
        if new_status in (FaultReport.STATUS_ASSIGNED, FaultReport.STATUS_ACCEPTED):
            valid = True
    elif old_status == FaultReport.STATUS_ASSIGNED:
        if new_status in (FaultReport.STATUS_ACCEPTED, FaultReport.STATUS_IN_PROGRESS, FaultReport.STATUS_OPEN):
            valid = True
    elif old_status == FaultReport.STATUS_ACCEPTED:
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

    # Determine actor & descriptive notes for history
    if not actor_name and fault.assigned_to:
        actor_name = fault.assigned_to.technician_profile.name if hasattr(fault.assigned_to, 'technician_profile') else (fault.assigned_to.get_full_name() or fault.assigned_to.username)

    if new_status == FaultReport.STATUS_ACCEPTED:
        note_text = "Technician accepted the fault"
    elif new_status == FaultReport.STATUS_IN_PROGRESS:
        note_text = "Technician started work"
    elif new_status == FaultReport.STATUS_RESOLVED:
        note_text = "Technician resolved the fault"
    elif new_status == FaultReport.STATUS_OPEN:
        note_text = "Reverted status to OPEN"
    else:
        note_text = f"Status updated to {new_status}"

    FaultStatusHistory.objects.create(
        fault=fault,
        status=new_status,
        actor_name=actor_name or "Supervisor",
        notes=note_text,
    )

    return fault


def _find_technician_by_phone(phone: str) -> Union[Technician, None]:
    """
    Looks up a Technician by phone number with flexible matching.
    """
    if not phone:
        return None
    clean = phone.strip()
    tech = Technician.objects.filter(phone_number=clean).first()
    if tech:
        return tech

    # Try matching without leading '+'
    no_plus = clean.lstrip('+')
    tech = Technician.objects.filter(phone_number__icontains=no_plus).first()
    if tech:
        return tech

    # Match by last 10 digits
    digits = ''.join(c for c in clean if c.isdigit())
    if len(digits) >= 10:
        last_10 = digits[-10:]
        for t in Technician.objects.exclude(phone_number=''):
            t_digits = ''.join(c for c in t.phone_number if c.isdigit())
            if t_digits.endswith(last_10):
                return t

    return None


def process_incoming_technician_sms(sender_phone: str, text: str) -> dict:
    """
    Processes an incoming SMS command from a technician.
    Supported commands:
      - ACCEPT <fault_id>
      - START <fault_id>
      - RESOLVE <fault_id>

    Returns a dict with 'status', 'response_message', and optional 'fault'.
    Sends a confirmation/reply SMS to the sender.
    """
    from .sms_service import send_sms

    clean_phone = (sender_phone or '').strip()[:20]
    clean_text = (text or '').strip()[:500]

    # 1. Look up technician
    technician = _find_technician_by_phone(clean_phone)
    if not technician:
        reply_msg = "FactoryPulse: Your phone number is not registered as a technician."
        send_sms(clean_phone, reply_msg)
        return {
            'status': 'error',
            'reason': 'technician_not_found',
            'response_message': reply_msg
        }

    # 2. Parse command
    parts = clean_text.split()
    cmd = parts[0].upper() if parts else ''

    if len(parts) < 2 or cmd not in ('ACCEPT', 'START', 'RESOLVE'):
        reply_msg = "FactoryPulse: Invalid command. Use ACCEPT <fault ID>, START <fault ID>, or RESOLVE <fault ID>."
        send_sms(clean_phone, reply_msg)
        return {
            'status': 'error',
            'reason': 'invalid_command',
            'response_message': reply_msg
        }

    try:
        fault_id = int(parts[1])
        if fault_id <= 0 or fault_id > 2147483647:
            raise ValueError("Fault ID out of range.")
    except (ValueError, OverflowError):
        reply_msg = "FactoryPulse: Invalid command. Use ACCEPT <fault ID>, START <fault ID>, or RESOLVE <fault ID>."
        send_sms(clean_phone, reply_msg)
        return {
            'status': 'error',
            'reason': 'invalid_fault_id',
            'response_message': reply_msg
        }

    # 3. Look up fault
    try:
        fault = FaultReport.objects.get(pk=fault_id)
    except (FaultReport.DoesNotExist, ValueError, OverflowError):
        reply_msg = f"FactoryPulse: Fault #{fault_id} not found."
        send_sms(clean_phone, reply_msg)
        return {
            'status': 'error',
            'reason': 'fault_not_found',
            'response_message': reply_msg
        }

    # 4. Validate ownership
    if fault.assigned_to != technician.user:
        reply_msg = f"FactoryPulse: Fault #{fault_id} is not assigned to you."
        send_sms(clean_phone, reply_msg)
        return {
            'status': 'error',
            'reason': 'unauthorized_fault',
            'response_message': reply_msg
        }

    # 5. Process command & enforce state transition rules
    try:
        if cmd == 'ACCEPT':
            if fault.status != FaultReport.STATUS_ASSIGNED:
                raise ValidationError(f"Fault #{fault_id} cannot be accepted from '{fault.get_status_display()}' status.")
            update_fault_status(fault.id, FaultReport.STATUS_ACCEPTED)
            reply_msg = f"FactoryPulse: Fault #{fault_id} accepted. You can start work using START {fault_id}."

        elif cmd == 'START':
            if fault.status not in (FaultReport.STATUS_ACCEPTED, FaultReport.STATUS_ASSIGNED):
                raise ValidationError(f"Fault #{fault_id} cannot be started from '{fault.get_status_display()}' status.")
            update_fault_status(fault.id, FaultReport.STATUS_IN_PROGRESS)
            reply_msg = f"FactoryPulse: Fault #{fault_id} is now IN PROGRESS."

        elif cmd == 'RESOLVE':
            if fault.status != FaultReport.STATUS_IN_PROGRESS:
                raise ValidationError(f"Fault #{fault_id} cannot be resolved from '{fault.get_status_display()}' status.")
            update_fault_status(fault.id, FaultReport.STATUS_RESOLVED)
            reply_msg = f"FactoryPulse: Fault #{fault_id} has been marked RESOLVED."

    except ValidationError as e:
        reply_msg = f"FactoryPulse: {e.message if hasattr(e, 'message') else str(e)}"
        send_sms(clean_phone, reply_msg)
        return {
            'status': 'error',
            'reason': 'invalid_transition',
            'response_message': reply_msg,
            'fault': fault
        }

    # Send success reply
    send_sms(clean_phone, reply_msg)
    return {
        'status': 'success',
        'command': cmd,
        'fault_id': fault_id,
        'response_message': reply_msg,
        'fault': fault
    }


def get_dashboard_stats(factory=None) -> dict:
    """
    Returns comprehensive fault statistics and intelligence for the dashboard,
    optionally filtered by factory.
    """
    qs = FaultReport.objects.all()
    if factory:
        qs = qs.filter(factory=factory)

    total = qs.count()
    open_count = qs.filter(status=FaultReport.STATUS_OPEN).count()
    assigned_count = qs.filter(status=FaultReport.STATUS_ASSIGNED).count()
    accepted_count = qs.filter(status=FaultReport.STATUS_ACCEPTED).count()
    in_progress_count = qs.filter(status=FaultReport.STATUS_IN_PROGRESS).count()
    critical_count = qs.filter(severity='Critical').count()
    resolved_count = qs.filter(status=FaultReport.STATUS_RESOLVED).count()

    today = timezone.now().date()

    history_qs = FaultStatusHistory.objects.filter(
        status=FaultReport.STATUS_RESOLVED,
        timestamp__date=today
    )
    if factory:
        history_qs = history_qs.filter(fault__factory=factory)

    resolved_today_ids = history_qs.values_list('fault_id', flat=True).distinct()
    resolved_today = resolved_today_ids.count()
    if resolved_today == 0:
        resolved_today = FaultReport.objects.filter(
            status=FaultReport.STATUS_RESOLVED,
            created_at__date=today
        ).count()

    # Breakdown by severity
    severity_breakdown = {
        'Low': FaultReport.objects.filter(severity='Low').count(),
        'Medium': FaultReport.objects.filter(severity='Medium').count(),
        'High': FaultReport.objects.filter(severity='High').count(),
        'Critical': critical_count,
    }

    # Breakdown by machine
    machine_counts_qs = FaultReport.objects.values('machine').annotate(count=Count('id')).order_by('-count')
    machine_breakdown = [
        {'machine': item['machine'], 'count': item['count']}
        for item in machine_counts_qs
    ]

    # Breakdown by status
    status_breakdown = {
        'OPEN': open_count,
        'ASSIGNED': assigned_count,
        'ACCEPTED': accepted_count,
        'IN_PROGRESS': in_progress_count,
        'RESOLVED': resolved_count,
    }

    downtime_data = get_downtime_analytics(now=timezone.now())

    return {
        'total_faults': total,
        'open_faults': open_count,
        'assigned_faults': assigned_count,
        'accepted_faults': accepted_count,
        'in_progress_faults': in_progress_count,
        'critical_faults': critical_count,
        'resolved_faults': resolved_count,
        'resolved_today': resolved_today,
        'severity_counts': severity_breakdown,
        'machine_counts': machine_breakdown,
        'status_counts': status_breakdown,
        'downtime': downtime_data,
    }


def format_duration(td: timedelta) -> str:
    """
    Formats a timedelta object into a clean, human-readable string.
    Examples: '2d 4h', '3h 15m', '45m', '0m'
    """
    if not td or td.total_seconds() <= 0:
        return '0m'

    total_seconds = int(td.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    if days > 0:
        return f"{days}d {hours}h" if hours > 0 else f"{days}d"
    elif hours > 0:
        return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
    else:
        return f"{minutes}m" if minutes > 0 else "0m"


def calculate_fault_downtime(fault: FaultReport, now=None) -> dict:
    """
    Calculates the exact downtime for a FaultReport using FaultStatusHistory timestamps.
    - If resolved: downtime = resolved_timestamp - initial_open_timestamp
    - If active: downtime = current_time - initial_open_timestamp
    """
    now_dt = now or timezone.now()

    # Find initial OPEN timestamp from history or fallback to created_at
    open_history = fault.history.filter(status=FaultReport.STATUS_OPEN).order_by('timestamp', 'id').first()
    open_time = open_history.timestamp if open_history else fault.created_at

    is_resolved = (fault.status == FaultReport.STATUS_RESOLVED)

    if is_resolved:
        resolved_history = fault.history.filter(status=FaultReport.STATUS_RESOLVED).order_by('-timestamp', '-id').first()
        resolved_time = resolved_history.timestamp if resolved_history else fault.created_at
        end_time = resolved_time
    else:
        resolved_time = None
        end_time = now_dt

    raw_duration = end_time - open_time
    duration = max(raw_duration, timedelta(seconds=0))

    return {
        'open_time': open_time,
        'resolved_time': resolved_time,
        'is_resolved': is_resolved,
        'duration': duration,
        'duration_seconds': int(duration.total_seconds()),
        'formatted_duration': format_duration(duration),
    }


def get_downtime_analytics(now=None) -> dict:
    """
    Calculates machine downtime aggregation, overall downtime summary, and critical active faults.
    """
    now_dt = now or timezone.now()

    # Prefetch all fault reports with history and assigned_to profile
    faults = FaultReport.objects.select_related(
        'assigned_to', 'assigned_to__technician_profile'
    ).prefetch_related('history').all()

    machine_stats = {}

    # Initialize entries for existing Machine models
    for m in Machine.objects.all():
        machine_stats[m.name] = {
            'machine': m.name,
            'total_faults': 0,
            'resolved_faults': 0,
            'active_faults': 0,
            'total_downtime_seconds': 0,
            'resolved_downtime_seconds': 0,
        }

    total_downtime_sec = 0
    total_resolved_downtime_sec = 0
    total_resolved_count = 0
    active_incidents_count = 0
    critical_incidents_count = 0
    critical_active_faults = []

    for f in faults:
        m_name = f.machine
        if m_name not in machine_stats:
            machine_stats[m_name] = {
                'machine': m_name,
                'total_faults': 0,
                'resolved_faults': 0,
                'active_faults': 0,
                'total_downtime_seconds': 0,
                'resolved_downtime_seconds': 0,
            }

        dt_info = calculate_fault_downtime(f, now=now_dt)
        sec = dt_info['duration_seconds']

        machine_stats[m_name]['total_faults'] += 1
        total_downtime_sec += sec

        if f.severity == 'Critical':
            critical_incidents_count += 1

        if dt_info['is_resolved']:
            machine_stats[m_name]['resolved_faults'] += 1
            machine_stats[m_name]['resolved_downtime_seconds'] += sec
            total_resolved_downtime_sec += sec
            total_resolved_count += 1
        else:
            machine_stats[m_name]['active_faults'] += 1
            active_incidents_count += 1

            if f.severity == 'Critical':
                tech_name = f.assigned_to.technician_profile.name if (f.assigned_to and hasattr(f.assigned_to, 'technician_profile')) else (f.assigned_to.username if f.assigned_to else "Unassigned")
                critical_active_faults.append({
                    'fault_id': f.id,
                    'machine': f.machine,
                    'problem': f.problem,
                    'assigned_technician': tech_name,
                    'status': f.status,
                    'status_display': f.get_status_display(),
                    'current_downtime': dt_info['formatted_duration'],
                })

        machine_stats[m_name]['total_downtime_seconds'] += sec

    # Build sorted machine breakdown list
    machine_downtime_list = []
    for m_name, m_data in machine_stats.items():
        res_count = m_data['resolved_faults']
        res_downtime_sec = m_data['resolved_downtime_seconds']
        avg_res_sec = int(res_downtime_sec / res_count) if res_count > 0 else 0

        machine_downtime_list.append({
            'machine': m_name,
            'total_faults': m_data['total_faults'],
            'resolved_faults': res_count,
            'active_faults': m_data['active_faults'],
            'total_downtime_seconds': m_data['total_downtime_seconds'],
            'formatted_downtime': format_duration(timedelta(seconds=m_data['total_downtime_seconds'])),
            'avg_resolution_seconds': avg_res_sec,
            'formatted_avg_resolution': format_duration(timedelta(seconds=avg_res_sec)),
        })

    # Sort machines by total_downtime_seconds descending
    machine_downtime_list.sort(key=lambda x: x['total_downtime_seconds'], reverse=True)

    # Most affected machine
    if machine_downtime_list and machine_downtime_list[0]['total_faults'] > 0:
        most_affected_machine = machine_downtime_list[0]['machine']
    else:
        most_affected_machine = "None"

    # Overall avg resolution time
    overall_avg_res_sec = int(total_resolved_downtime_sec / total_resolved_count) if total_resolved_count > 0 else 0

    return {
        'total_downtime_seconds': total_downtime_sec,
        'formatted_total_downtime': format_duration(timedelta(seconds=total_downtime_sec)),
        'avg_resolution_seconds': overall_avg_res_sec,
        'formatted_avg_resolution': format_duration(timedelta(seconds=overall_avg_res_sec)),
        'active_incidents': active_incidents_count,
        'most_affected_machine': most_affected_machine,
        'critical_incidents': critical_incidents_count,
        'machine_downtime_list': machine_downtime_list,
        'critical_active_faults': critical_active_faults,
    }


def get_recent_activity() -> list:
    """
    Returns recent activities based on FaultReport objects.
    """
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
        elif r.status == FaultReport.STATUS_ASSIGNED and r.assigned_to:
            tech_name = r.assigned_to.technician_profile.name if hasattr(r.assigned_to, 'technician_profile') else r.assigned_to.get_full_name() or r.assigned_to.username
            activity.append({
                'time': timestamp,
                'message': f"Fault #{r.id} assigned to {tech_name}",
                'machine': r.machine,
                'detail': f"{r.severity} severity",
            })
        else:
            activity.append({
                'time': timestamp,
                'message': f"Fault #{r.id} reported",
                'machine': r.machine,
                'detail': f"{r.severity} severity",
            })
            
    return activity
