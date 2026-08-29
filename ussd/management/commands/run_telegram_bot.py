"""
Django management command to run the FactoryPulse Telegram development bot.

Usage:
    python manage.py run_telegram_bot
"""

import os
import logging
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from ussd.telegram_bot import build_telegram_application

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Start the FactoryPulse Telegram development bot (polling mode)'

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            raise CommandError(
                "TELEGRAM_BOT_TOKEN is not configured.\n"
                "Set it in your .env file:\n"
                "  TELEGRAM_BOT_TOKEN=your-bot-token-here\n\n"
                "Get a token from @BotFather on Telegram."
            )

        # Allow synchronous Django ORM calls from async telegram handlers.
        # This is safe for a single-process development bot.
        os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'

        self.stdout.write(self.style.SUCCESS(
            "🏭 FactoryPulse Telegram Bot starting...\n"
            "   Press Ctrl+C to stop.\n"
        ))

        application = build_telegram_application(token)
        application.run_polling(drop_pending_updates=True)
