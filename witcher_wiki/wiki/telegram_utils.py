import hashlib
import hmac
import json
from urllib.parse import parse_qs
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.utils import timezone
from .models import TelegramUser, UserProfile
import secrets


class TelegramAuth:
    def __init__(self, bot_token):
        self.bot_token = bot_token

    def verify_telegram_webapp_data(self, init_data):
        """
        Проверяет подпись данных от Telegram Web App
        """
        try:
            # Парсим данные
            parsed_data = parse_qs(init_data)

            # Извлекаем хеш
            received_hash = parsed_data.get('hash', [''])[0]

            # Убираем хеш из данных для проверки
            data_check_string_parts = []
            for key, value in sorted(parsed_data.items()):
                if key != 'hash':
                    data_check_string_parts.append(f"{key}={value[0]}")

            data_check_string = '\n'.join(data_check_string_parts)

            # Вычисляем секретный ключ
            secret_key = hmac.new(
                b"WebAppData",
                msg=self.bot_token.encode(),
                digestmod=hashlib.sha256
            ).digest()

            # Вычисляем хеш
            computed_hash = hmac.new(
                secret_key,
                msg=data_check_string.encode(),
                digestmod=hashlib.sha256
            ).hexdigest()

            # Сравниваем хеши
            if computed_hash != received_hash:
                return False, None

            # Извлекаем данные пользователя
            user_data = {
                'id': int(parsed_data.get('id', [0])[0]),
                'first_name': parsed_data.get('first_name', [''])[0],
                'last_name': parsed_data.get('last_name', [''])[0],
                'username': parsed_data.get('username', [''])[0],
                'photo_url': parsed_data.get('photo_url', [''])[0],
                'auth_date': int(parsed_data.get('auth_date', [0])[0]),
                'hash': received_hash
            }

            return True, user_data

        except Exception as e:
            print(f"Telegram WebApp auth error: {e}")
            return False, None

    def authenticate_user(self, request, user_data):
        """
        Аутентифицирует пользователя на основе данных Telegram
        """
        try:
            telegram_id = user_data['id']

            # Ищем пользователя по telegram_id
            telegram_user = TelegramUser.objects.filter(telegram_id=telegram_id).first()

            if telegram_user:
                # Пользователь найден - логиним его
                user = telegram_user.user
                login(request, user)

                # Обновляем данные
                telegram_user.telegram_username = user_data.get('username', '')
                telegram_user.first_name = user_data.get('first_name', '')
                telegram_user.last_name = user_data.get('last_name', '')
                telegram_user.photo_url = user_data.get('photo_url', '')
                telegram_user.auth_date = timezone.datetime.fromtimestamp(user_data['auth_date'], tz=timezone.utc)
                telegram_user.hash = user_data.get('hash', '')
                telegram_user.web_app_data = user_data
                telegram_user.save()

                return user, False  # Существующий пользователь
            else:
                # Пользователь не найден - создаем нового
                username = self.generate_username(user_data)
                email = f"telegram_{telegram_id}@witcher.wiki"

                # Создаем пользователя Django
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=secrets.token_urlsafe(16)  # Случайный пароль
                )
                user.first_name = user_data.get('first_name', '')[:30]
                user.last_name = user_data.get('last_name', '')[:30]
                user.save()

                # Создаем профиль пользователя
                UserProfile.objects.get_or_create(user=user)

                # Создаем привязку к Telegram
                telegram_user = TelegramUser.objects.create(
                    user=user,
                    telegram_id=telegram_id,
                    telegram_username=user_data.get('username', ''),
                    first_name=user_data.get('first_name', ''),
                    last_name=user_data.get('last_name', ''),
                    photo_url=user_data.get('photo_url', ''),
                    auth_date=timezone.datetime.fromtimestamp(user_data['auth_date'], tz=timezone.utc),
                    hash=user_data.get('hash', ''),
                    web_app_data=user_data
                )

                login(request, user)
                return user, True  # Новый пользователь

        except Exception as e:
            print(f"Authentication error: {e}")
            return None, False

    def generate_username(self, user_data):
        """
        Генерирует уникальное имя пользователя на основе данных Telegram
        """
        base_username = user_data.get('username') or f"user{user_data['id']}"
        username = base_username

        # Проверяем уникальность
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1

        return username

    def connect_telegram_account(self, user, user_data):
        """
        Привязывает Telegram аккаунт к существующему пользователю
        """
        telegram_id = user_data['id']

        # Проверяем, не привязан ли уже этот Telegram аккаунт
        if TelegramUser.objects.filter(telegram_id=telegram_id).exists():
            raise ValueError("Этот Telegram аккаунт уже привязан к другому пользователю")

        # Проверяем, не привязан ли уже Telegram к этому пользователю
        if hasattr(user, 'telegram_account'):
            raise ValueError("У этого пользователя уже привязан Telegram аккаунт")

        # Создаем привязку
        telegram_user = TelegramUser.objects.create(
            user=user,
            telegram_id=telegram_id,
            telegram_username=user_data.get('username', ''),
            first_name=user_data.get('first_name', ''),
            last_name=user_data.get('last_name', ''),
            photo_url=user_data.get('photo_url', ''),
            auth_date=timezone.datetime.fromtimestamp(user_data['auth_date'], tz=timezone.utc),
            hash=user_data.get('hash', ''),
            web_app_data=user_data
        )

        return telegram_user