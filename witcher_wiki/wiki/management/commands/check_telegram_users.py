from django.core.management.base import BaseCommand
from wiki.models import TelegramUser, User


class Command(BaseCommand):
    help = 'Проверка привязанных Telegram аккаунтов'

    def handle(self, *args, **options):
        telegram_users = TelegramUser.objects.all()

        self.stdout.write(f'📊 Найдено привязанных аккаунтов: {telegram_users.count()}')

        for tg_user in telegram_users:
            self.stdout.write(f'   • {tg_user.user.username} -> Telegram ID: {tg_user.telegram_id}')

        if telegram_users.count() == 0:
            self.stdout.write(
                self.style.WARNING('⚠️ Нет привязанных аккаунтов. Используйте команду /auth в боте для привязки.')
            )