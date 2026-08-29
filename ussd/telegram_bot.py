"""
FactoryPulse Telegram Development Bot

Provides a Telegram interface for testing the same fault-reporting workflow
that will eventually be accessed through Africa's Talking USSD.

Architecture: Telegram -> services -> database

Note: Django ORM calls are made directly from async handlers. This requires
DJANGO_ALLOW_ASYNC_UNSAFE=true to be set in the environment, which the
management command handles automatically.
"""

import logging
import re
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from .services import (
    get_ussd_machine_list,
    PROBLEMS,
    SEVERITIES,
    resolve_machine,
    resolve_problem,
    resolve_severity,
    create_fault_report,
    get_user_fault_reports,
    get_machine_statuses,
)

logger = logging.getLogger(__name__)

# Conversation states
MAIN_MENU, SELECT_MACHINE, SELECT_PROBLEM, DESCRIBE_PROBLEM, SELECT_SEVERITY, CONFIRMATION = range(6)


# ── Keyboard helpers ──────────────────────────────────────────────────────────

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            ['1. 🚨 Report Fault'],
            ['2. 🔧 Check Machine'],
            ['3. 📋 My Reports'],
        ],
        one_time_keyboard=True,
        resize_keyboard=True,
    )


def machine_keyboard():
    machines = get_ussd_machine_list()
    rows = [[f"{key}. {name}"] for key, name in machines.items()]
    rows.append(['Cancel'])
    return ReplyKeyboardMarkup(rows, one_time_keyboard=True, resize_keyboard=True)


def problem_keyboard():
    rows = [[f"{key}. {desc}"] for key, desc in PROBLEMS.items()]
    rows.append(['4. Other'])
    rows.append(['Cancel'])
    return ReplyKeyboardMarkup(rows, one_time_keyboard=True, resize_keyboard=True)


def severity_keyboard():
    rows = [[f"{key}. {name}"] for key, name in SEVERITIES.items()]
    rows.append(['Cancel'])
    return ReplyKeyboardMarkup(rows, one_time_keyboard=True, resize_keyboard=True)


def confirmation_keyboard():
    return ReplyKeyboardMarkup(
        [['1. Submit'], ['2. Cancel']],
        one_time_keyboard=True,
        resize_keyboard=True,
    )


# ── Handler functions ─────────────────────────────────────────────────────────

async def start_command(update: Update, context) -> int:
    """Handle /start command - show main menu."""
    context.user_data.clear()
    await update.message.reply_text(
        "🏭 *FactoryPulse*\n\n"
        "Factory maintenance assistant.\n\n"
        "Choose an option:\n\n"
        "1. 🚨 Report Fault\n"
        "2. 🔧 Check Machine\n"
        "3. 📋 My Reports",
        reply_markup=main_menu_keyboard(),
        parse_mode='Markdown',
    )
    return MAIN_MENU


async def handle_main_menu(update: Update, context) -> int:
    """Route user from main menu to the chosen feature."""
    text = (update.message.text or '').strip()

    # Normalize: extract leading digit
    choice = text[0] if text and text[0] in ('1', '2', '3') else None

    if choice == '1':
        # Report Fault
        await update.message.reply_text(
            "Select Machine:\n\n"
            "1. Generator\n"
            "2. Packaging Machine\n"
            "3. Milling Machine",
            reply_markup=machine_keyboard(),
        )
        return SELECT_MACHINE

    elif choice == '2':
        # Check Machine
        return await handle_check_machine(update, context)

    elif choice == '3':
        # My Reports
        return await handle_my_reports(update, context)

    else:
        await update.message.reply_text(
            "❌ Invalid option. Please choose 1, 2, or 3.",
            reply_markup=main_menu_keyboard(),
        )
        return MAIN_MENU


async def handle_machine_selection(update: Update, context) -> int:
    """Parse machine selection and prompt for problem."""
    text = (update.message.text or '').strip()
    machine = resolve_machine(text)

    if not machine:
        await update.message.reply_text(
            "❌ Invalid machine. Please select a valid option.\n\n"
            "Select Machine:\n\n"
            "1. Generator\n"
            "2. Packaging Machine\n"
            "3. Milling Machine",
            reply_markup=machine_keyboard(),
        )
        return SELECT_MACHINE

    context.user_data['machine'] = machine
    await update.message.reply_text(
        "Select Problem:\n\n"
        "1. Not working\n"
        "2. Overheating\n"
        "3. Making noise\n"
        "4. Other",
        reply_markup=problem_keyboard(),
    )
    return SELECT_PROBLEM


async def handle_problem_selection(update: Update, context) -> int:
    """Parse problem selection and prompt for severity (or custom description)."""
    text = (update.message.text or '').strip()
    problem = resolve_problem(text)

    if problem is None:
        await update.message.reply_text(
            "❌ Invalid option. Please select a valid problem.\n\n"
            "Select Problem:\n\n"
            "1. Not working\n"
            "2. Overheating\n"
            "3. Making noise\n"
            "4. Other",
            reply_markup=problem_keyboard(),
        )
        return SELECT_PROBLEM

    if problem == 'OTHER':
        await update.message.reply_text(
            "Describe the problem:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return DESCRIBE_PROBLEM

    context.user_data['problem'] = problem
    await update.message.reply_text(
        "Select Severity:\n\n"
        "1. Low\n"
        "2. Medium\n"
        "3. High\n"
        "4. Critical",
        reply_markup=severity_keyboard(),
    )
    return SELECT_SEVERITY


async def handle_describe_problem(update: Update, context) -> int:
    """Store custom problem description and prompt for severity."""
    text = (update.message.text or '').strip()

    if not text:
        await update.message.reply_text(
            "❌ Please provide a description of the problem:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return DESCRIBE_PROBLEM

    context.user_data['problem'] = text
    await update.message.reply_text(
        "Select Severity:\n\n"
        "1. Low\n"
        "2. Medium\n"
        "3. High\n"
        "4. Critical",
        reply_markup=severity_keyboard(),
    )
    return SELECT_SEVERITY


async def handle_severity_selection(update: Update, context) -> int:
    """Parse severity selection and show confirmation summary."""
    text = (update.message.text or '').strip()
    severity = resolve_severity(text)

    if not severity:
        await update.message.reply_text(
            "❌ Invalid severity. Please select a valid option.\n\n"
            "Select Severity:\n\n"
            "1. Low\n"
            "2. Medium\n"
            "3. High\n"
            "4. Critical",
            reply_markup=severity_keyboard(),
        )
        return SELECT_SEVERITY

    context.user_data['severity'] = severity
    machine = context.user_data.get('machine', '?')
    problem = context.user_data.get('problem', '?')

    await update.message.reply_text(
        f"📋 *Fault Report*\n\n"
        f"Machine: {machine}\n"
        f"Problem: {problem}\n"
        f"Severity: {severity}\n\n"
        f"1. Submit\n"
        f"2. Cancel",
        reply_markup=confirmation_keyboard(),
        parse_mode='Markdown',
    )
    return CONFIRMATION


async def handle_confirmation(update: Update, context) -> int:
    """Handle Submit or Cancel at confirmation step."""
    text = (update.message.text or '').strip()

    # Normalize: extract leading digit
    choice = text[0] if text and text[0] in ('1', '2') else None

    if choice == '1':
        # Submit
        user = update.effective_user
        fault = create_fault_report(
            machine=context.user_data.get('machine', ''),
            problem=context.user_data.get('problem', ''),
            severity=context.user_data.get('severity', ''),
            telegram_user_id=str(user.id),
            telegram_username=user.username or '',
        )
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ Fault report submitted.\n\n"
            f"Fault ID: #{fault.id}\n"
            f"Status: {fault.status}",
            reply_markup=main_menu_keyboard(),
        )
        return MAIN_MENU

    elif choice == '2':
        # Cancel
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Fault report cancelled.",
            reply_markup=main_menu_keyboard(),
        )
        return MAIN_MENU

    else:
        await update.message.reply_text(
            "❌ Invalid option. Please choose:\n\n"
            "1. Submit\n"
            "2. Cancel",
            reply_markup=confirmation_keyboard(),
        )
        return CONFIRMATION


async def handle_check_machine(update: Update, context) -> int:
    """Display predefined machine statuses."""
    statuses = get_machine_statuses()
    lines = ["🔧 *Machines*\n"]
    for m in statuses:
        lines.append(f"{m['id']}. {m['name']} - {m['status']}")

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=main_menu_keyboard(),
        parse_mode='Markdown',
    )
    return MAIN_MENU


async def handle_my_reports(update: Update, context) -> int:
    """Show the current Telegram user's own fault reports only."""
    user = update.effective_user
    user_id_str = str(user.id)

    reports = list(get_user_fault_reports(telegram_user_id=user_id_str)[:20])

    if not reports:
        await update.message.reply_text(
            "📋 *My Reports*\n\n"
            "You have no fault reports yet.",
            reply_markup=main_menu_keyboard(),
            parse_mode='Markdown',
        )
        return MAIN_MENU

    lines = ["📋 *My Reports*\n"]
    for r in reports:
        lines.append(
            f"#{r.id}\n"
            f"{r.machine}\n"
            f"{r.problem}\n"
            f"{r.severity}\n"
            f"Status: {r.status}\n"
        )

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=main_menu_keyboard(),
        parse_mode='Markdown',
    )
    return MAIN_MENU


async def cancel_command(update: Update, context) -> int:
    """Handle /cancel command or Cancel button at any step."""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Operation cancelled.\n\n"
        "🏭 *FactoryPulse*\n\n"
        "Choose an option:\n\n"
        "1. 🚨 Report Fault\n"
        "2. 🔧 Check Machine\n"
        "3. 📋 My Reports",
        reply_markup=main_menu_keyboard(),
        parse_mode='Markdown',
    )
    return MAIN_MENU


def build_conversation_handler() -> ConversationHandler:
    """Build the ConversationHandler for the fault-reporting workflow."""
    cancel_handler = CommandHandler('cancel', cancel_command)
    cancel_button_handler = MessageHandler(
        filters.Regex(re.compile(r'^(cancel|/cancel)$', re.IGNORECASE)), cancel_command
    )

    return ConversationHandler(
        entry_points=[CommandHandler('start', start_command)],
        states={
            MAIN_MENU: [
                cancel_handler,
                cancel_button_handler,
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu),
            ],
            SELECT_MACHINE: [
                cancel_handler,
                cancel_button_handler,
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_machine_selection),
            ],
            SELECT_PROBLEM: [
                cancel_handler,
                cancel_button_handler,
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_problem_selection),
            ],
            DESCRIBE_PROBLEM: [
                cancel_handler,
                cancel_button_handler,
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_describe_problem),
            ],
            SELECT_SEVERITY: [
                cancel_handler,
                cancel_button_handler,
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_severity_selection),
            ],
            CONFIRMATION: [
                cancel_handler,
                cancel_button_handler,
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation),
            ],
        },
        fallbacks=[
            cancel_handler,
            cancel_button_handler,
        ],
    )


def build_telegram_application(token: str = None) -> Application:
    """
    Factory function to create and configure the Telegram Application.
    If no token is provided, reads from Django settings.
    """
    if not token:
        from django.conf import settings
        token = settings.TELEGRAM_BOT_TOKEN

    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN is not configured. "
            "Set it in your .env file or environment variables."
        )

    application = Application.builder().token(token).build()
    application.add_handler(build_conversation_handler())
    return application
