"""
Africa's Talking SMS Service for FactoryPulse

Handles outgoing SMS notifications to technicians and supervisors.

IMPLEMENTATION NOTE:
The africastalking Python SDK uses requests/urllib3 internally.
On Python 3.14 + OpenSSL 3.0.18, urllib3's create_urllib3_context()
creates an SSL context that fails against Africa's Talking's TLS
certificates (WRONG_VERSION_NUMBER / CERTIFICATE_VERIFY_FAILED).

Python's stdlib http.client.HTTPSConnection works perfectly, so we
call the AT REST API directly via http.client, bypassing the SDK's
broken SSL path. The API contract is identical:

    POST https://api.sandbox.africastalking.com/version1/messaging
    Headers: Accept: application/json, apiKey: <key>
    Body:    username=<user>&to=<phone>&message=<msg>&bulkSMSMode=1
"""

import http.client
import json
import logging
import os
import ssl
import urllib.parse

from django.conf import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# API hosts (from AT SDK source: Service.py / APIService)              #
# ------------------------------------------------------------------ #
_SANDBOX_HOST = "api.sandbox.africastalking.com"
_PRODUCTION_HOST = "api.africastalking.com"
_MESSAGING_PATH = "/version1/messaging"


def _mask_phone(phone: str) -> str:
    """Returns a safely masked phone number, e.g. +234*******678"""
    phone = (phone or '').strip()
    if len(phone) <= 4:
        return '****'
    return phone[:3] + '*' * (len(phone) - 7) + phone[-4:]


def _get_at_config() -> dict:
    """
    Returns Africa's Talking configuration from Django settings.
    Never returns the raw API key in logs.
    """
    username = getattr(
        settings, 'AFRICASTALKING_USERNAME',
        os.environ.get('AFRICASTALKING_USERNAME', 'sandbox')
    )
    api_key = getattr(
        settings, 'AFRICASTALKING_API_KEY',
        os.environ.get('AFRICASTALKING_API_KEY', '')
    )
    return {'username': username, 'api_key': api_key}


def send_sms(recipient: str, message: str) -> dict:
    """
    Sends an SMS via Africa's Talking REST API using stdlib http.client.
    Bypasses the AT SDK to avoid urllib3 SSL context issues on Python 3.14.

    Returns:
        {'status': 'sent', 'response': <parsed JSON>}
        {'status': 'skipped', 'reason': '...'}
        {'status': 'failed', 'error': '...'}
    """
    clean_phone = (recipient or '').strip()
    masked = _mask_phone(clean_phone)

    if not clean_phone:
        logger.warning("[SMS] Attempted to send SMS with an empty recipient phone number.")
        return {'status': 'skipped', 'reason': 'No phone number'}

    config = _get_at_config()
    username = config['username']
    api_key = config['api_key']

    logger.debug(
        f"[SMS] Preparing to send SMS | recipient={masked} | "
        f"username='{username}' | api_key_configured={'YES' if api_key else 'NO'}"
    )

    if not api_key:
        logger.warning("[SMS] AFRICASTALKING_API_KEY is not configured. SMS will not be dispatched.")
        return {'status': 'skipped', 'reason': 'API key not configured'}

    # Determine host (sandbox vs production)
    is_sandbox = (username == 'sandbox')
    host = _SANDBOX_HOST if is_sandbox else _PRODUCTION_HOST

    # Build form-encoded POST body (matching SDK: Service.py __make_post_request)
    post_data = urllib.parse.urlencode({
        'username': username,
        'to': clean_phone,
        'message': message,
        'bulkSMSMode': '1',
    })

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
        'apiKey': api_key,
    }

    try:
        logger.debug(f"[SMS] Connecting to {host}:443 (TLS) → POST {_MESSAGING_PATH}")

        # Use stdlib SSL context — proven to work with AT's certificates
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(host, 443, timeout=15, context=ctx)
        conn.request('POST', _MESSAGING_PATH, body=post_data, headers=headers)
        resp = conn.getresponse()

        status_code = resp.status
        body = resp.read().decode('utf-8', errors='replace')
        conn.close()

        logger.info(f"[SMS] AT API HTTP response | status_code={status_code} | recipient={masked}")

        # Parse JSON response
        try:
            response_data = json.loads(body)
        except json.JSONDecodeError:
            response_data = {'raw': body}

        # ------------------------------------------------------------------ #
        # AT SMS response structure:                                            #
        # {"SMSMessageData": {"Message": "...", "Recipients": [                #
        #   {"statusCode": 101, "status": "Success", "messageId": "...", ...}  #
        # ]}}                                                                   #
        # ------------------------------------------------------------------ #
        sms_data = response_data.get('SMSMessageData', {}) if isinstance(response_data, dict) else {}
        at_message = sms_data.get('Message', 'n/a')
        recipients = sms_data.get('Recipients', [])

        logger.info(
            f"[SMS] AT API response body | "
            f"message='{at_message}' | recipients_count={len(recipients)}"
        )

        for r in recipients:
            msg_id = r.get('messageId', 'n/a')
            r_status = r.get('status', 'n/a')
            r_code = r.get('statusCode', 'n/a')
            cost = r.get('cost', 'n/a')
            logger.info(
                f"[SMS] Recipient result | phone={masked} | "
                f"status_code={r_code} | status={r_status} | "
                f"message_id={msg_id} | cost={cost}"
            )

        if not recipients:
            logger.warning(
                f"[SMS] AT returned no recipients for {masked} | "
                f"http_status={status_code} | raw_message='{at_message}'"
            )

        if 200 <= status_code < 300:
            return {'status': 'sent', 'response': response_data}
        else:
            logger.error(
                f"[SMS] AT API returned HTTP {status_code} | recipient={masked} | body={body[:300]}"
            )
            return {'status': 'failed', 'error': f'HTTP {status_code}', 'response': response_data}

    except Exception as e:
        logger.error(
            f"[SMS] Exception calling AT API | "
            f"recipient={masked} | error_type={type(e).__name__} | detail={e}"
        )
        return {'status': 'failed', 'error': str(e)}


def send_technician_assignment_sms(fault, technician) -> bool:
    """
    Constructs and sends an assignment SMS notification to a technician.
    Returns True if sent successfully, False otherwise.
    """
    logger.debug(
        f"[SMS] send_technician_assignment_sms called | "
        f"fault_id={fault.id} | "
        f"technician={getattr(technician, 'name', 'None')} | "
        f"has_phone={'YES' if getattr(technician, 'phone_number', None) else 'NO'}"
    )

    if not technician or not getattr(technician, 'phone_number', None):
        logger.info(
            f"[SMS] Skipping — technician for fault #{fault.id} has no registered phone number."
        )
        return False

    masked = _mask_phone(technician.phone_number)
    logger.info(
        f"[SMS] Composing assignment SMS | "
        f"fault_id={fault.id} | "
        f"machine='{fault.machine}' | "
        f"problem='{fault.problem}' | "
        f"severity='{fault.severity}' | "
        f"recipient={masked}"
    )

    message = (
        f"FactoryPulse\n\n"
        f"Fault #{fault.id} has been assigned to you.\n\n"
        f"Machine: {fault.machine}\n"
        f"Problem: {fault.problem}\n"
        f"Severity: {fault.severity.upper()}\n\n"
        f"Please review this task."
    )

    result = send_sms(technician.phone_number, message)
    success = result.get('status') == 'sent'

    if success:
        logger.info(f"[SMS] Assignment SMS dispatched successfully | fault_id={fault.id} | recipient={masked}")
    else:
        logger.warning(
            f"[SMS] Assignment SMS NOT sent | fault_id={fault.id} | "
            f"recipient={masked} | result_status={result.get('status')} | detail={result}"
        )

    return success
