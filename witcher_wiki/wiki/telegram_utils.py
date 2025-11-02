import hashlib
import hmac
import json
from django.contrib.auth.models import User
from .models import TelegramUser, UserProfile

class TelegramAuth:
    """Класс для аутентификации через Telegram"""

    def __init__(self, bot_token):
        self.bot_token = bot_token

    def verify_telegram_data(self, init_data):
        """
        Проверяет подпись данных от Telegram Web App
        """
        try:
            # Парсим данные
            data_pairs = init_data.split('&')
            data_dict = {}
            hash_value = None

            for pair in data_pairs:
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    if key == 'hash':
                        hash_value = value
                    else:
                        data_dict[key] = value

            if not hash_value:
                return False, "Hash not found"

            # Сортируем данные и создаем строку для проверки
            data_check_string = '\n'.join(
                f"{key}={value}"
                for key, value in sorted(data_dict.items())
            )

            # Вычисляем секретный ключ
            secret_key = hmac.new(
                b"WebAppData",
                self.bot_token.encode(),
                hashlib.sha256
            ).digest()

            # Проверяем подпись
            computed_hash = hmac.new(
                secret_key,
                data_check_string.encode(),
                hashlib.sha256
            ).hexdigest()

            if computed_hash != hash_value:
                return False, "Invalid hash"

            # Парсим user данные
            user_data_str = data_dict.get('user', '{}')
            user_data = json.loads(user_data_str)
            return True, user_data

        except Exception as e:
            return False, str(e)

    def create_or_get_user(self, telegram_data):
        """
        Создает или получает пользователя по данным Telegram
        """
        telegram_id = telegram_data.get('id')
        username = telegram_data.get('username', '')
        first_name = telegram_data.get('first_name', '')
        last_name = telegram_data.get('last_name', '')
        photo_url = telegram_data.get('photo_url', '')

        # Проверяем, есть ли уже привязанный пользователь
        try:
            telegram_user = TelegramUser.objects.get(telegram_id=telegram_id)
            return telegram_user.user, False  # Пользователь существует

        except TelegramUser.DoesNotExist:
            # Создаем нового пользователя
            if username:
                django_username = f"tg_{username}"
            else:
                django_username = f"tg_user_{telegram_id}"

            # Проверяем уникальность username
            counter = 1
            original_username = django_username
            while User.objects.filter(username=django_username).exists():
                django_username = f"{original_username}_{counter}"
                counter += 1

            # Создаем пользователя Django
            user = User.objects.create_user(
                username=django_username,
                email=f"{django_username}@telegram.user",
                password=None  # Пароль не нужен для Telegram входа
            )
            user.first_name = first_name
            user.last_name = last_name
            user.save()

            # Создаем профиль Telegram
            telegram_user = TelegramUser.objects.create(
                user=user,
                telegram_id=telegram_id,
                telegram_username=username,
                first_name=first_name,
                last_name=last_name,
                photo_url=photo_url
            )

            # Создаем UserProfile
            UserProfile.objects.get_or_create(user=user)

            return user, True  # Новый пользователь