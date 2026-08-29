"""
Tests for the FactoryPulse Telegram bot (ussd/telegram_bot.py).

Uses mocked Telegram objects — does NOT contact the real Telegram API.
Service layer functions are mocked in handler tests to avoid async/DB conflicts.
Service layer correctness is verified separately in test_services.py.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from django.test import TestCase, override_settings
from django.core.management import call_command
from django.core.management.base import CommandError

from ussd.models import FaultReport
from ussd.telegram_bot import (
    MAIN_MENU, SELECT_MACHINE, SELECT_PROBLEM,
    DESCRIBE_PROBLEM, SELECT_SEVERITY, CONFIRMATION,
    start_command, handle_main_menu, handle_machine_selection,
    handle_problem_selection, handle_describe_problem,
    handle_severity_selection, handle_confirmation,
    handle_check_machine, handle_my_reports, cancel_command,
    build_conversation_handler, build_telegram_application,
)


def run_async(coro):
    """Helper to run async coroutines in sync test methods."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def make_update(text='', user_id=12345, username='testuser'):
    """Create a mock Telegram Update object."""
    update = MagicMock()
    update.message = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.username = username
    return update


def make_context():
    """Create a mock context with user_data dict."""
    context = MagicMock()
    context.user_data = {}
    return context


def make_fake_fault(id=1, machine='Generator', problem='Overheating',
                    severity='High', status='OPEN', telegram_user_id='12345',
                    telegram_username='testuser'):
    """Create a fake FaultReport-like object for mocking."""
    fault = MagicMock()
    fault.id = id
    fault.machine = machine
    fault.problem = problem
    fault.severity = severity
    fault.status = status
    fault.telegram_user_id = telegram_user_id
    fault.telegram_username = telegram_username
    return fault


class TelegramBotConfigTests(TestCase):
    """Tests for Telegram bot configuration."""

    @override_settings(TELEGRAM_BOT_TOKEN='test-token-123')
    def test_build_application_with_settings_token(self):
        app = build_telegram_application()
        self.assertIsNotNone(app)

    def test_build_application_with_explicit_token(self):
        app = build_telegram_application(token='explicit-token-456')
        self.assertIsNotNone(app)

    @override_settings(TELEGRAM_BOT_TOKEN='')
    def test_build_application_raises_without_token(self):
        with self.assertRaises(ValueError):
            build_telegram_application()

    def test_conversation_handler_structure(self):
        handler = build_conversation_handler()
        self.assertIsNotNone(handler)
        self.assertTrue(len(handler.entry_points) > 0)


class StartCommandTests(TestCase):
    """Tests for the /start command."""

    def test_start_returns_main_menu(self):
        update = make_update('/start')
        context = make_context()
        result = run_async(start_command(update, context))
        self.assertEqual(result, MAIN_MENU)
        update.message.reply_text.assert_called_once()
        call_text = update.message.reply_text.call_args[0][0]
        self.assertIn('FactoryPulse', call_text)
        self.assertIn('Report Fault', call_text)
        self.assertIn('Check Machine', call_text)
        self.assertIn('My Reports', call_text)

    def test_start_clears_user_data(self):
        update = make_update('/start')
        context = make_context()
        context.user_data = {'machine': 'Generator', 'problem': 'test'}
        run_async(start_command(update, context))
        self.assertEqual(context.user_data, {})


class MainMenuTests(TestCase):
    """Tests for main menu routing."""

    def test_select_report_fault(self):
        update = make_update('1')
        context = make_context()
        result = run_async(handle_main_menu(update, context))
        self.assertEqual(result, SELECT_MACHINE)

    def test_select_report_fault_button(self):
        update = make_update('1. 🚨 Report Fault')
        context = make_context()
        result = run_async(handle_main_menu(update, context))
        self.assertEqual(result, SELECT_MACHINE)

    @patch('ussd.telegram_bot.get_machine_statuses')
    def test_select_check_machine(self, mock_statuses):
        mock_statuses.return_value = [
            {'id': '1', 'name': 'Generator', 'status': 'Operational'},
            {'id': '2', 'name': 'Packaging Machine', 'status': 'Operational'},
            {'id': '3', 'name': 'Milling Machine', 'status': 'Operational'},
        ]
        update = make_update('2')
        context = make_context()
        result = run_async(handle_main_menu(update, context))
        self.assertEqual(result, MAIN_MENU)
        call_text = update.message.reply_text.call_args[0][0]
        self.assertIn('Machines', call_text)

    @patch('ussd.telegram_bot.get_user_fault_reports')
    def test_select_my_reports(self, mock_reports):
        qs_mock = MagicMock()
        qs_mock.__getitem__ = MagicMock(return_value=[])
        mock_reports.return_value = qs_mock

        update = make_update('3')
        context = make_context()
        result = run_async(handle_main_menu(update, context))
        self.assertEqual(result, MAIN_MENU)

    def test_invalid_menu_option(self):
        update = make_update('9')
        context = make_context()
        result = run_async(handle_main_menu(update, context))
        self.assertEqual(result, MAIN_MENU)
        call_text = update.message.reply_text.call_args[0][0]
        self.assertIn('Invalid', call_text)


class MachineSelectionTests(TestCase):
    """Tests for machine selection step."""

    def test_machine_selection_valid(self):
        update = make_update('1')
        context = make_context()
        result = run_async(handle_machine_selection(update, context))
        self.assertEqual(result, SELECT_PROBLEM)
        self.assertEqual(context.user_data['machine'], 'Generator')

    def test_machine_selection_by_label(self):
        update = make_update('2. Packaging Machine')
        context = make_context()
        result = run_async(handle_machine_selection(update, context))
        self.assertEqual(result, SELECT_PROBLEM)
        self.assertEqual(context.user_data['machine'], 'Packaging Machine')

    def test_machine_selection_invalid(self):
        update = make_update('9')
        context = make_context()
        result = run_async(handle_machine_selection(update, context))
        self.assertEqual(result, SELECT_MACHINE)
        call_text = update.message.reply_text.call_args[0][0]
        self.assertIn('Invalid', call_text)


class ProblemSelectionTests(TestCase):
    """Tests for problem selection step."""

    def test_problem_selection_valid(self):
        update = make_update('2')
        context = make_context()
        result = run_async(handle_problem_selection(update, context))
        self.assertEqual(result, SELECT_SEVERITY)
        self.assertEqual(context.user_data['problem'], 'Overheating')

    def test_problem_selection_other(self):
        update = make_update('4')
        context = make_context()
        result = run_async(handle_problem_selection(update, context))
        self.assertEqual(result, DESCRIBE_PROBLEM)

    def test_problem_selection_invalid(self):
        update = make_update('9')
        context = make_context()
        result = run_async(handle_problem_selection(update, context))
        self.assertEqual(result, SELECT_PROBLEM)
        call_text = update.message.reply_text.call_args[0][0]
        self.assertIn('Invalid', call_text)

    def test_describe_problem(self):
        update = make_update('Conveyor belt broken')
        context = make_context()
        result = run_async(handle_describe_problem(update, context))
        self.assertEqual(result, SELECT_SEVERITY)
        self.assertEqual(context.user_data['problem'], 'Conveyor belt broken')

    def test_describe_problem_empty(self):
        update = make_update('')
        context = make_context()
        result = run_async(handle_describe_problem(update, context))
        self.assertEqual(result, DESCRIBE_PROBLEM)


class SeveritySelectionTests(TestCase):
    """Tests for severity selection step."""

    def test_severity_selection_valid(self):
        update = make_update('3')
        context = make_context()
        context.user_data = {'machine': 'Generator', 'problem': 'Overheating'}
        result = run_async(handle_severity_selection(update, context))
        self.assertEqual(result, CONFIRMATION)
        self.assertEqual(context.user_data['severity'], 'High')
        call_text = update.message.reply_text.call_args[0][0]
        self.assertIn('Generator', call_text)
        self.assertIn('Overheating', call_text)
        self.assertIn('High', call_text)

    def test_severity_selection_invalid(self):
        update = make_update('9')
        context = make_context()
        context.user_data = {'machine': 'Generator', 'problem': 'Overheating'}
        result = run_async(handle_severity_selection(update, context))
        self.assertEqual(result, SELECT_SEVERITY)
        call_text = update.message.reply_text.call_args[0][0]
        self.assertIn('Invalid', call_text)


class ConfirmationTests(TestCase):
    """Tests for confirmation step — service layer is mocked."""

    @patch('ussd.telegram_bot.create_fault_report')
    def test_confirmation_submit(self, mock_create):
        """Submitting confirmation calls create_fault_report and shows Fault ID."""
        fake_fault = make_fake_fault(id=42)
        mock_create.return_value = fake_fault

        update = make_update('1', user_id=99999, username='submituser')
        context = make_context()
        context.user_data = {
            'machine': 'Generator',
            'problem': 'Overheating',
            'severity': 'High',
        }
        result = run_async(handle_confirmation(update, context))
        self.assertEqual(result, MAIN_MENU)

        # Verify service was called with correct args
        mock_create.assert_called_once_with(
            machine='Generator',
            problem='Overheating',
            severity='High',
            telegram_user_id='99999',
            telegram_username='submituser',
        )

        call_text = update.message.reply_text.call_args[0][0]
        self.assertIn('Fault ID: #42', call_text)
        self.assertIn('OPEN', call_text)

        # user_data should be cleared after submit
        self.assertEqual(context.user_data, {})

    @patch('ussd.telegram_bot.create_fault_report')
    def test_confirmation_submit_button_label(self, mock_create):
        """Submit also works when sent as '1. Submit' button text."""
        mock_create.return_value = make_fake_fault(id=7)

        update = make_update('1. Submit', user_id=88888, username='btn_user')
        context = make_context()
        context.user_data = {
            'machine': 'Milling Machine',
            'problem': 'Not working',
            'severity': 'Critical',
        }
        result = run_async(handle_confirmation(update, context))
        self.assertEqual(result, MAIN_MENU)
        mock_create.assert_called_once()

    def test_confirmation_cancel(self):
        """Cancelling at confirmation clears user_data and does NOT call service."""
        update = make_update('2')
        context = make_context()
        context.user_data = {
            'machine': 'Generator',
            'problem': 'Overheating',
            'severity': 'High',
        }
        result = run_async(handle_confirmation(update, context))
        self.assertEqual(result, MAIN_MENU)
        self.assertEqual(context.user_data, {})
        call_text = update.message.reply_text.call_args[0][0]
        self.assertIn('cancelled', call_text)

    def test_confirmation_invalid(self):
        update = make_update('9')
        context = make_context()
        context.user_data = {
            'machine': 'Generator',
            'problem': 'Overheating',
            'severity': 'High',
        }
        result = run_async(handle_confirmation(update, context))
        self.assertEqual(result, CONFIRMATION)
        call_text = update.message.reply_text.call_args[0][0]
        self.assertIn('Invalid', call_text)


class FullReportFlowEndToEndTests(TestCase):
    """End-to-end conversation flow test (service layer mocked)."""

    @patch('ussd.telegram_bot.create_fault_report')
    def test_full_flow_generator_overheating_high(self, mock_create):
        fake_fault = make_fake_fault(
            id=1, machine='Generator', problem='Overheating',
            severity='High', telegram_user_id='77777',
        )
        mock_create.return_value = fake_fault
        context = make_context()
        user_id = 77777
        username = 'e2euser'

        # Step 1: /start
        update = make_update('/start', user_id=user_id, username=username)
        result = run_async(start_command(update, context))
        self.assertEqual(result, MAIN_MENU)

        # Step 2: Select Report Fault
        update = make_update('1', user_id=user_id, username=username)
        result = run_async(handle_main_menu(update, context))
        self.assertEqual(result, SELECT_MACHINE)

        # Step 3: Select Generator
        update = make_update('1', user_id=user_id, username=username)
        result = run_async(handle_machine_selection(update, context))
        self.assertEqual(result, SELECT_PROBLEM)

        # Step 4: Select Overheating
        update = make_update('2', user_id=user_id, username=username)
        result = run_async(handle_problem_selection(update, context))
        self.assertEqual(result, SELECT_SEVERITY)

        # Step 5: Select High
        update = make_update('3', user_id=user_id, username=username)
        result = run_async(handle_severity_selection(update, context))
        self.assertEqual(result, CONFIRMATION)

        # Step 6: Submit
        update = make_update('1', user_id=user_id, username=username)
        result = run_async(handle_confirmation(update, context))
        self.assertEqual(result, MAIN_MENU)

        # Verify service was called correctly
        mock_create.assert_called_once_with(
            machine='Generator',
            problem='Overheating',
            severity='High',
            telegram_user_id=str(user_id),
            telegram_username=username,
        )

        call_text = update.message.reply_text.call_args[0][0]
        self.assertIn('Fault ID: #1', call_text)
        self.assertIn('OPEN', call_text)

    @patch('ussd.telegram_bot.create_fault_report')
    def test_full_flow_other_problem(self, mock_create):
        """Test flow with custom 'Other' problem description."""
        mock_create.return_value = make_fake_fault(
            id=2, machine='Packaging Machine',
            problem='Motor vibrating excessively', severity='Critical',
        )
        context = make_context()
        user_id = 66666

        update = make_update('1', user_id=user_id)
        run_async(handle_main_menu(update, context))

        update = make_update('2', user_id=user_id)
        run_async(handle_machine_selection(update, context))

        update = make_update('4', user_id=user_id)
        result = run_async(handle_problem_selection(update, context))
        self.assertEqual(result, DESCRIBE_PROBLEM)

        update = make_update('Motor vibrating excessively', user_id=user_id)
        result = run_async(handle_describe_problem(update, context))
        self.assertEqual(result, SELECT_SEVERITY)

        update = make_update('4', user_id=user_id)
        run_async(handle_severity_selection(update, context))

        update = make_update('1', user_id=user_id)
        run_async(handle_confirmation(update, context))

        mock_create.assert_called_once_with(
            machine='Packaging Machine',
            problem='Motor vibrating excessively',
            severity='Critical',
            telegram_user_id=str(user_id),
            telegram_username='testuser',
        )


class UserIsolationTests(TestCase):
    """Telegram user isolation — User A must never see User B's reports."""

    @patch('ussd.telegram_bot.get_user_fault_reports')
    def test_user_a_sees_only_own_reports(self, mock_reports):
        fault_a = make_fake_fault(id=10, machine='Generator', problem='Not working',
                                  severity='High', telegram_user_id='1001')
        mock_reports.return_value = MagicMock(
            __getitem__=MagicMock(return_value=[fault_a])
        )
        # Make list(qs[:20]) return [fault_a]
        mock_reports.return_value.__getitem__.return_value = [fault_a]

        update = make_update('3', user_id=1001, username='user_a')
        context = make_context()
        result = run_async(handle_my_reports(update, context))
        self.assertEqual(result, MAIN_MENU)

        # Verify called with correct user ID
        mock_reports.assert_called_once_with(telegram_user_id='1001')

        call_text = update.message.reply_text.call_args[0][0]
        self.assertIn('Generator', call_text)

    @patch('ussd.telegram_bot.get_user_fault_reports')
    def test_user_b_sees_only_own_reports(self, mock_reports):
        fault_b = make_fake_fault(id=20, machine='Milling Machine',
                                  problem='Overheating', severity='Critical',
                                  telegram_user_id='2002')
        mock_reports.return_value = MagicMock(
            __getitem__=MagicMock(return_value=[fault_b])
        )
        mock_reports.return_value.__getitem__.return_value = [fault_b]

        update = make_update('3', user_id=2002, username='user_b')
        context = make_context()
        result = run_async(handle_my_reports(update, context))
        self.assertEqual(result, MAIN_MENU)

        mock_reports.assert_called_once_with(telegram_user_id='2002')

        call_text = update.message.reply_text.call_args[0][0]
        self.assertIn('Milling Machine', call_text)
        self.assertNotIn('Generator', call_text)

    @patch('ussd.telegram_bot.get_user_fault_reports')
    def test_unknown_user_sees_nothing(self, mock_reports):
        # Return an empty result that evaluates to falsy list
        mock_reports.return_value = MagicMock(
            __getitem__=MagicMock(return_value=[])
        )
        mock_reports.return_value.__getitem__.return_value = []

        update = make_update('3', user_id=9999, username='nobody')
        context = make_context()
        result = run_async(handle_my_reports(update, context))
        self.assertEqual(result, MAIN_MENU)
        call_text = update.message.reply_text.call_args[0][0]
        self.assertIn('no fault reports', call_text)


class MyReportsTests(TestCase):
    """Tests for My Reports display formatting."""

    @patch('ussd.telegram_bot.get_user_fault_reports')
    def test_my_reports_empty(self, mock_reports):
        mock_reports.return_value = MagicMock(
            __getitem__=MagicMock(return_value=[])
        )
        mock_reports.return_value.__getitem__.return_value = []

        update = make_update('3', user_id=5555)
        context = make_context()
        result = run_async(handle_my_reports(update, context))
        self.assertEqual(result, MAIN_MENU)
        call_text = update.message.reply_text.call_args[0][0]
        self.assertIn('no fault reports', call_text)

    @patch('ussd.telegram_bot.get_user_fault_reports')
    def test_my_reports_displays_details(self, mock_reports):
        fault = make_fake_fault(id=42, machine='Generator', problem='Overheating',
                                severity='High', status='OPEN')
        mock_reports.return_value = MagicMock(
            __getitem__=MagicMock(return_value=[fault])
        )
        mock_reports.return_value.__getitem__.return_value = [fault]

        update = make_update('3', user_id=5555)
        context = make_context()
        run_async(handle_my_reports(update, context))
        call_text = update.message.reply_text.call_args[0][0]
        self.assertIn('#42', call_text)
        self.assertIn('Generator', call_text)
        self.assertIn('Overheating', call_text)
        self.assertIn('High', call_text)
        self.assertIn('OPEN', call_text)


class CheckMachineTests(TestCase):
    """Tests for Check Machine feature."""

    @patch('ussd.telegram_bot.get_machine_statuses')
    def test_check_machine_shows_statuses(self, mock_statuses):
        mock_statuses.return_value = [
            {'id': '1', 'name': 'Generator', 'status': 'Operational'},
            {'id': '2', 'name': 'Packaging Machine', 'status': 'Operational'},
            {'id': '3', 'name': 'Milling Machine', 'status': 'Operational'},
        ]
        update = make_update('2')
        context = make_context()
        result = run_async(handle_check_machine(update, context))
        self.assertEqual(result, MAIN_MENU)
        call_text = update.message.reply_text.call_args[0][0]
        self.assertIn('Generator', call_text)
        self.assertIn('Packaging Machine', call_text)
        self.assertIn('Milling Machine', call_text)
        self.assertIn('Operational', call_text)


class CancelTests(TestCase):
    """Tests for cancel command and cancel button."""

    def test_cancel_command_returns_main_menu(self):
        update = make_update('/cancel')
        context = make_context()
        context.user_data = {'machine': 'Generator', 'problem': 'test'}
        result = run_async(cancel_command(update, context))
        self.assertEqual(result, MAIN_MENU)
        self.assertEqual(context.user_data, {})
        call_text = update.message.reply_text.call_args[0][0]
        self.assertIn('cancelled', call_text)

    def test_cancel_at_machine_step(self):
        """Cancel during machine selection clears data."""
        update = make_update('/cancel')
        context = make_context()
        context.user_data = {'some_key': 'value'}
        result = run_async(cancel_command(update, context))
        self.assertEqual(result, MAIN_MENU)
        self.assertEqual(context.user_data, {})

    def test_cancel_does_not_create_report(self):
        """Cancelling mid-flow must not leave a DB record."""
        update = make_update('/cancel')
        context = make_context()
        context.user_data = {
            'machine': 'Generator',
            'problem': 'Overheating',
            'severity': 'High',
        }
        run_async(cancel_command(update, context))
        self.assertEqual(FaultReport.objects.count(), 0)


class ManagementCommandTests(TestCase):
    """Tests for the run_telegram_bot management command."""

    @override_settings(TELEGRAM_BOT_TOKEN='')
    def test_command_raises_without_token(self):
        with self.assertRaises(CommandError):
            call_command('run_telegram_bot')

    @override_settings(TELEGRAM_BOT_TOKEN='test-token-for-cmd')
    @patch('ussd.management.commands.run_telegram_bot.build_telegram_application')
    def test_command_starts_with_token(self, mock_build):
        mock_app = MagicMock()
        mock_build.return_value = mock_app
        call_command('run_telegram_bot', stdout=MagicMock())
        mock_build.assert_called_once_with('test-token-for-cmd')
        mock_app.run_polling.assert_called_once()
