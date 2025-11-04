# management/commands/telegram_auth.py
from django.core.management.base import BaseCommand
from wiki.telegram_auth_manager import TelegramAuthManager


class Command(BaseCommand):
    help = 'Управление кодами авторизации Telegram'

    def add_arguments(self, parser):
        parser.add_argument('action', choices=['generate-code', 'list-codes', 'cleanup'])

    def handle(self, *args, **options):
        action = options['action']

        if action == 'generate-code':
            # Генерируем тестовый код
            test_data = {
                'id': 123456789,
                'username': 'test_user',
                'first_name': 'Test User'
            }
            code = TelegramAuthManager.generate_auth_code(test_data)
            self.stdout.write(
                self.style.SUCCESS(f'✅ Сгенерирован код: {code}')
            )

        elif action == 'list-codes':
            codes = TelegramAuthManager.get_pending_codes()
            if codes:
                self.stdout.write("📋 Активные коды:")
                for auth_code in codes:
                    self.stdout.write(f"  • {auth_code.code} - {auth_code.telegram_username}")
            else:
                self.stdout.write("ℹ️ Нет активных кодов")

        elif action == 'cleanup':
            # Очистка выполняется автоматически в get_pending_codes
            codes = TelegramAuthManager.get_pending_codes()
            self.stdout.write(
                self.style.SUCCESS('✅ База данных очищена от просроченных кодов')
            )