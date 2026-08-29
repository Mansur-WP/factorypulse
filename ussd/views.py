import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import FaultReport
from .services import get_ussd_machine_list, PROBLEMS, SEVERITIES, create_fault_report

logger = logging.getLogger(__name__)




@csrf_exempt
@require_POST
def ussd_callback(request):
    """
    Africa's Talking USSD callback endpoint.
    Handles multi-step USSD navigation using cumulative request text.
    """
    try:
        session_id = request.POST.get('sessionId', '')
        service_code = request.POST.get('serviceCode', '')
        phone_number = request.POST.get('phoneNumber', '')
        text = request.POST.get('text', '').strip()

        # Load machines dynamically from the database
        machines = get_ussd_machine_list()

        # Initial session start
        if not text:
            response = (
                "CON Welcome to FactoryPulse\n\n"
                "1. Report Fault\n"
                "2. Check Machine\n"
                "3. My Reports"
            )
            return HttpResponse(response, content_type='text/plain')

        tokens = [t.strip() for t in text.split('*')]

        # Check for cancellation at any stage
        if tokens[-1] == '0':
            return HttpResponse("END Fault report cancelled.", content_type='text/plain')

        first_choice = tokens[0]

        if first_choice == '1':
            # Report Fault Flow State Machine
            step = 'SELECT_MACHINE'
            machine = None
            problem = None
            severity = None
            invalid_flag = False

            for token in tokens[1:]:
                if token == '0':
                    return HttpResponse("END Fault report cancelled.", content_type='text/plain')

                if step == 'SELECT_MACHINE':
                    if token in machines:
                        machine = machines[token]
                        step = 'SELECT_PROBLEM'
                        invalid_flag = False
                    else:
                        invalid_flag = True

                elif step == 'SELECT_PROBLEM':
                    if token in PROBLEMS:
                        problem = PROBLEMS[token]
                        step = 'SELECT_SEVERITY'
                        invalid_flag = False
                    elif token == '4':
                        step = 'DESCRIBE_PROBLEM'
                        invalid_flag = False
                    else:
                        invalid_flag = True

                elif step == 'DESCRIBE_PROBLEM':
                    if token:
                        problem = token
                        step = 'SELECT_SEVERITY'
                        invalid_flag = False
                    else:
                        invalid_flag = True

                elif step == 'SELECT_SEVERITY':
                    if token in SEVERITIES:
                        severity = SEVERITIES[token]
                        step = 'CONFIRMATION'
                        invalid_flag = False
                    else:
                        invalid_flag = True

                elif step == 'CONFIRMATION':
                    if token == '1':
                        fault = create_fault_report(
                            phone_number=phone_number,
                            machine=machine,
                            problem=problem,
                            severity=severity,
                            status=FaultReport.STATUS_OPEN,
                        )
                        return HttpResponse(
                            f"END Fault report submitted successfully.\n\nFault ID: #{fault.id}",
                            content_type='text/plain',
                        )
                    elif token == '2':
                        return HttpResponse("END Fault report cancelled.", content_type='text/plain')
                    else:
                        invalid_flag = True

            # Render corresponding step UI
            prefix = "CON Invalid option.\n\n" if invalid_flag else "CON "

            if step == 'SELECT_MACHINE':
                # Build machine menu dynamically from database
                machine_lines = "\n".join(f"{k}. {v}" for k, v in machines.items())
                body = f"Select Machine\n\n{machine_lines}"
            elif step == 'SELECT_PROBLEM':
                body = "What is the problem?\n\n1. Not working\n2. Overheating\n3. Making noise\n4. Other"
            elif step == 'DESCRIBE_PROBLEM':
                body = "Describe the problem:"
            elif step == 'SELECT_SEVERITY':
                body = "Select severity\n\n1. Low\n2. Medium\n3. High\n4. Critical"
            elif step == 'CONFIRMATION':
                body = (
                    f"Report Summary\n\n"
                    f"Machine: {machine}\n"
                    f"Problem: {problem}\n"
                    f"Severity: {severity}\n\n"
                    f"1. Submit\n"
                    f"2. Cancel"
                )
            else:
                body = "An error occurred."

            return HttpResponse(prefix + body, content_type='text/plain')

        elif first_choice in ('2', '3'):
            return HttpResponse("END Feature coming soon.", content_type='text/plain')
        else:
            return HttpResponse(
                "CON Invalid option.\n\n"
                "Welcome to FactoryPulse\n\n"
                "1. Report Fault\n"
                "2. Check Machine\n"
                "3. My Reports",
                content_type='text/plain',
            )

    except Exception as e:
        logger.exception(f"USSD callback error: {e}")
        return HttpResponse(
            "END An error occurred. Please try again.",
            content_type='text/plain',
        )


@csrf_exempt
@require_POST
def sms_delivery_callback(request):
    """
    Africa's Talking SMS Delivery Status callback.
    POST /sms/delivery/

    Africa's Talking will POST:
      - id          : Unique message ID
      - status      : e.g. "Success", "Failed", "Sent", "Rejected"
      - phoneNumber : Recipient phone number
      - failureReason (optional): Reason for failure

    We log the delivery event. We do not claim that "Success" means the
    technician read the SMS — only that the network accepted delivery.
    """
    msg_id = request.POST.get('id', 'unknown')
    status = request.POST.get('status', 'unknown')
    phone = request.POST.get('phoneNumber', 'unknown')
    failure_reason = request.POST.get('failureReason', '')

    if status.lower() in ('success', 'delivered'):
        logger.info(f"SMS delivery confirmed: msg_id={msg_id}, phone={phone}")
    elif failure_reason:
        logger.warning(
            f"SMS delivery failed: msg_id={msg_id}, phone={phone}, "
            f"status={status}, reason={failure_reason}"
        )
    else:
        logger.info(f"SMS delivery update: msg_id={msg_id}, phone={phone}, status={status}")

    return HttpResponse("OK", status=200, content_type='text/plain')


@csrf_exempt
@require_POST
def sms_incoming_callback(request):
    """
    Africa's Talking Incoming SMS webhook endpoint.
    POST /sms/incoming/

    Africa's Talking POSTs:
      - from  : Sender phone number (e.g. "+2349012345678")
      - to    : Shortcode / receiver number
      - text  : SMS message body (e.g. "ACCEPT 9", "START 9", "RESOLVE 9")
      - date  : Timestamp
      - id    : Unique message ID
    """
    from_phone = request.POST.get('from', '').strip()
    text = request.POST.get('text', '').strip()
    msg_id = request.POST.get('id', '')

    logger.info(f"Incoming SMS received: id={msg_id}, from={from_phone}, text='{text}'")

    from .services import process_incoming_technician_sms
    result = process_incoming_technician_sms(sender_phone=from_phone, text=text)

    logger.info(f"Incoming SMS processing result: {result.get('status')} - {result.get('reason', 'ok')}")
    return HttpResponse("OK", status=200, content_type='text/plain')


