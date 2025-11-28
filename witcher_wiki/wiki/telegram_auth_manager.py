import secrets
import time
from django.db import transaction
from django.utils import timezone
from .models import AuthCode, TelegramUser, User


class TelegramAuthManager:
    """Менеджер авторизации Telegram через базу данных"""

    @classmethod
    def generate_auth_code(cls, telegram_user_data):
        """Генерирует код авторизации и сохраняет в базу"""
        code = str(secrets.randbelow(900000) + 100000)  # 6-значный код

        # Сохраняем в базу
        auth_code = AuthCode.objects.create(
            code=code,
            telegram_id=telegram_user_data['id'],
            telegram_username=telegram_user_data.get('username', ''),
            first_name=telegram_user_data.get('first_name', ''),
            expires_at=time.time() + 600  # 10 минут
        )

        return code

    @classmethod
    def verify_auth_code(cls, code, django_user):
        """Проверяет код и привязывает аккаунт"""
        try:
            auth_code = AuthCode.objects.get(
                code=code,
                is_used=False
            )

            # Проверяем срок действия
            if time.time() > auth_code.expires_at:
                auth_code.delete()
                return False, "Срок действия кода истек"

            # Привязываем Telegram аккаунт
            with transaction.atomic():
                # Создаем или обновляем привязку
                telegram_user, created = TelegramUser.objects.get_or_create(
                    telegram_id=auth_code.telegram_id,
                    defaults={
                        'user': django_user,
                        'telegram_username': auth_code.telegram_username,
                        'first_name': auth_code.first_name,
                        'auth_date': timezone.now()
                    }
                )

                if not created:
                    # Если аккаунт уже привязан к другому пользователю
                    if telegram_user.user != django_user:
                        return False, "Этот Telegram аккаунт уже привязан к другому пользователю"

                # Помечаем код как использованный
                auth_code.is_used = True
                auth_code.used_by = django_user
                auth_code.used_at = timezone.now()
                auth_code.save()

                return True, "Аккаунт успешно привязан"

        except AuthCode.DoesNotExist:
            return False, "Неверный код авторизации"

    @classmethod
    def get_pending_codes(cls):
        """Возвращает активные коды авторизации"""
        # Удаляем просроченные коды
        AuthCode.objects.filter(expires_at__lt=time.time()).delete()

        return AuthCode.objects.filter(is_used=False)