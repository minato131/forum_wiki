from django.core.management.base import BaseCommand
import asyncio
from wiki.telegram_bot import bot
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Запускает Telegram бота'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🤖 Запуск Telegram бота...')
        )

        try:
            # Запускаем бота
            asyncio.run(bot.run())
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('⏹️ Остановка бота...')
            )
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка: {e}')
            )