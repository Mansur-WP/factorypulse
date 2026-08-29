"""
Tests for the FactoryPulse shared services layer (ussd/services.py).
"""

from django.test import TestCase
from ussd.models import FaultReport
from ussd.services import (
    MACHINES, PROBLEMS, SEVERITIES,
    resolve_machine, resolve_problem, resolve_severity,
    create_fault_report, get_user_fault_reports, get_machine_statuses,
)


class ResolveHelperTests(TestCase):
    """Tests for input resolution helper functions."""

    # ── resolve_machine ───────────────────────────────────────────────────

    def test_resolve_machine_by_digit(self):
        self.assertEqual(resolve_machine('1'), 'Generator')
        self.assertEqual(resolve_machine('2'), 'Packaging Machine')
        self.assertEqual(resolve_machine('3'), 'Milling Machine')

    def test_resolve_machine_by_label(self):
        self.assertEqual(resolve_machine('1. Generator'), 'Generator')
        self.assertEqual(resolve_machine('2. Packaging Machine'), 'Packaging Machine')

    def test_resolve_machine_by_name(self):
        self.assertEqual(resolve_machine('Generator'), 'Generator')
        self.assertEqual(resolve_machine('generator'), 'Generator')

    def test_resolve_machine_invalid(self):
        self.assertIsNone(resolve_machine('9'))
        self.assertIsNone(resolve_machine(''))
        self.assertIsNone(resolve_machine('xyz'))

    # ── resolve_problem ───────────────────────────────────────────────────

    def test_resolve_problem_by_digit(self):
        self.assertEqual(resolve_problem('1'), 'Not working')
        self.assertEqual(resolve_problem('2'), 'Overheating')
        self.assertEqual(resolve_problem('3'), 'Making noise')

    def test_resolve_problem_other(self):
        self.assertEqual(resolve_problem('4'), 'OTHER')
        self.assertEqual(resolve_problem('4. Other'), 'OTHER')

    def test_resolve_problem_by_name(self):
        self.assertEqual(resolve_problem('Not working'), 'Not working')
        self.assertEqual(resolve_problem('overheating'), 'Overheating')

    def test_resolve_problem_invalid(self):
        self.assertIsNone(resolve_problem('9'))
        self.assertIsNone(resolve_problem(''))

    # ── resolve_severity ──────────────────────────────────────────────────

    def test_resolve_severity_by_digit(self):
        self.assertEqual(resolve_severity('1'), 'Low')
        self.assertEqual(resolve_severity('2'), 'Medium')
        self.assertEqual(resolve_severity('3'), 'High')
        self.assertEqual(resolve_severity('4'), 'Critical')

    def test_resolve_severity_by_label(self):
        self.assertEqual(resolve_severity('3. High'), 'High')

    def test_resolve_severity_by_name(self):
        self.assertEqual(resolve_severity('Critical'), 'Critical')
        self.assertEqual(resolve_severity('low'), 'Low')

    def test_resolve_severity_invalid(self):
        self.assertIsNone(resolve_severity('9'))
        self.assertIsNone(resolve_severity(''))
        self.assertIsNone(resolve_severity('xyz'))


class CreateFaultReportServiceTests(TestCase):
    """Tests for the create_fault_report service function."""

    def test_create_fault_report_with_phone(self):
        fault = create_fault_report(
            machine='Generator',
            problem='Overheating',
            severity='High',
            phone_number='+2348012345678',
        )
        self.assertIsNotNone(fault.id)
        self.assertEqual(fault.machine, 'Generator')
        self.assertEqual(fault.problem, 'Overheating')
        self.assertEqual(fault.severity, 'High')
        self.assertEqual(fault.phone_number, '+2348012345678')
        self.assertEqual(fault.status, FaultReport.STATUS_OPEN)

    def test_create_fault_report_with_telegram(self):
        fault = create_fault_report(
            machine='Milling Machine',
            problem='Making noise',
            severity='Critical',
            telegram_user_id='123456789',
            telegram_username='testuser',
        )
        self.assertIsNotNone(fault.id)
        self.assertEqual(fault.telegram_user_id, '123456789')
        self.assertEqual(fault.telegram_username, 'testuser')
        self.assertEqual(fault.phone_number, '')

    def test_create_fault_report_defaults(self):
        fault = create_fault_report(
            machine='Generator',
            problem='Not working',
            severity='Low',
        )
        self.assertEqual(fault.status, FaultReport.STATUS_OPEN)
        self.assertEqual(fault.phone_number, '')
        self.assertEqual(fault.telegram_user_id, '')
        self.assertEqual(fault.telegram_username, '')


class GetUserFaultReportsTests(TestCase):
    """Tests for the get_user_fault_reports service function."""

    def setUp(self):
        self.fault_tg = create_fault_report(
            machine='Generator', problem='Not working', severity='High',
            telegram_user_id='111',
        )
        self.fault_tg2 = create_fault_report(
            machine='Milling Machine', problem='Overheating', severity='Low',
            telegram_user_id='111',
        )
        self.fault_other = create_fault_report(
            machine='Packaging Machine', problem='Making noise', severity='Medium',
            telegram_user_id='222',
        )
        self.fault_phone = create_fault_report(
            machine='Generator', problem='Not working', severity='Critical',
            phone_number='+2348000000000',
        )

    def test_get_reports_by_telegram_user(self):
        reports = get_user_fault_reports(telegram_user_id='111')
        self.assertEqual(reports.count(), 2)
        for r in reports:
            self.assertEqual(r.telegram_user_id, '111')

    def test_user_isolation_telegram(self):
        """User 111 must NOT see user 222's reports."""
        reports = get_user_fault_reports(telegram_user_id='111')
        report_ids = list(reports.values_list('id', flat=True))
        self.assertNotIn(self.fault_other.id, report_ids)

    def test_get_reports_by_phone(self):
        reports = get_user_fault_reports(phone_number='+2348000000000')
        self.assertEqual(reports.count(), 1)
        self.assertEqual(reports.first().phone_number, '+2348000000000')

    def test_get_reports_no_identifier(self):
        reports = get_user_fault_reports()
        self.assertEqual(reports.count(), 0)


class GetMachineStatusesTests(TestCase):
    """Tests for the get_machine_statuses service function."""

    def test_returns_all_machines(self):
        statuses = get_machine_statuses()
        self.assertEqual(len(statuses), 3)
        names = [m['name'] for m in statuses]
        self.assertIn('Generator', names)
        self.assertIn('Packaging Machine', names)
        self.assertIn('Milling Machine', names)

    def test_all_operational(self):
        statuses = get_machine_statuses()
        for m in statuses:
            self.assertEqual(m['status'], 'Operational')
