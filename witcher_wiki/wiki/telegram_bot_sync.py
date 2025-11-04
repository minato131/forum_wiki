import os
import django
import logging
import requests
import time
import json
from django.conf import settings
from django.db.models import Q, Sum

# Настройка Django ДО импорта моделей
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'witcher_wiki.settings')
django.setup()

# Теперь импортируем модели
from wiki.models import TelegramUser, Article, User

logger = logging.getLogger(__name__)
class SyncTelegramBot:
    def __init__(self):
        self.token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if not self.token:
            logger.error("❌ TELEGRAM_BOT_TOKEN не настроен в settings.py")
            return

        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = 0
        self.error_count = 0
        self.max_errors = 5

class TelegramAuthManager:
    """Менеджер авторизации Telegram через базу данных"""

    @classmethod
    def generate_auth_code(cls, telegram_user_data):
        """Генерирует код авторизации и сохраняет в базу"""
        from wiki.models import AuthCode
        import time

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
        from wiki.models import AuthCode
        import time

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
                        'auth_date': time.time()
                    }
                )

                if not created:
                    # Если аккаунт уже привязан к другому пользователю
                    if telegram_user.user != django_user:
                        return False, "Этот Telegram аккаунт уже привязан к другому пользователю"

                # Помечаем код как использованный
                auth_code.is_used = True
                auth_code.used_by = django_user
                auth_code.used_at = time.time()
                auth_code.save()

                return True, "Аккаунт успешно привязан"

        except AuthCode.DoesNotExist:
            return False, "Неверный код авторизации"

    @classmethod
    def get_pending_codes(cls):
        """Возвращает активные коды авторизации"""
        from wiki.models import AuthCode
        import time

        # Удаляем просроченные коды
        AuthCode.objects.filter(expires_at__lt=time.time()).delete()

        return AuthCode.objects.filter(is_used=False)

class SyncTelegramBot:
    def __init__(self):
        self.token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if not self.token:
            logger.error("❌ TELEGRAM_BOT_TOKEN не настроен в settings.py")
            return

        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = 0
        self.error_count = 0
        self.max_errors = 5

        # Хранилище временных кодов авторизации
        self.auth_codes = {}  # {user_id: {'code': '123456', 'timestamp': time.time()}}

        # Проверим токен при инициализации
        self.check_bot_token()

    def check_bot_token(self):
        """Проверяет валидность токена бота"""
        try:
            url = f"{self.base_url}/getMe"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                bot_info = response.json()
                logger.info(f"✅ Бот подключен: {bot_info['result']['first_name']} (@{bot_info['result']['username']})")
                return True
            else:
                logger.error(f"❌ Неверный токен бота: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки токена: {e}")
            return False

    def get_updates(self):
        """Получает обновления от Telegram с обработкой ошибок"""
        try:
            url = f"{self.base_url}/getUpdates"
            params = {
                'offset': self.last_update_id + 1,
                'timeout': 10,
                'limit': 100
            }
            response = requests.get(url, params=params, timeout=15)

            if response.status_code == 409:
                logger.error("❌ Другой бот уже запущен с этим токеном! Остановите другие процессы.")
                return []
            elif response.status_code == 401:
                logger.error("❌ Неверный токен бота! Проверьте TELEGRAM_BOT_TOKEN в settings.py")
                return []

            response.raise_for_status()
            self.error_count = 0
            return response.json().get('result', [])

        except requests.exceptions.RequestException as e:
            self.error_count += 1
            logger.error(f"Ошибка получения updates ({self.error_count}/{self.max_errors}): {e}")

            if self.error_count >= self.max_errors:
                logger.error("❌ Слишком много ошибок. Перезапустите бота.")
                raise
            return []
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
            return []

    def send_message(self, chat_id, text, reply_markup=None):
        """Отправляет сообщение с улучшенной обработкой ошибок"""
        try:
            url = f"{self.base_url}/sendMessage"

            # Подготавливаем данные
            data = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML'
            }

            # Добавляем клавиатуру если есть
            if reply_markup:
                data['reply_markup'] = json.dumps(reply_markup)

            # Логируем что отправляем (для отладки)
            logger.debug(f"Отправка сообщения в chat_id: {chat_id}")

            response = requests.post(url, json=data, timeout=10)

            if response.status_code == 400:
                # Bad Request - попробуем без HTML разметки
                logger.warning("❌ Ошибка 400, пробуем без HTML...")
                data['parse_mode'] = None
                response = requests.post(url, json=data, timeout=10)

            response.raise_for_status()

            logger.debug(f"✅ Сообщение отправлено успешно")
            return True

        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP ошибка при отправке сообщения: {e}")
            logger.error(f"Response: {response.text}")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка отправки сообщения: {e}")
            return False

    def create_inline_keyboard(self, buttons):
        """Создает inline клавиатуру"""
        if not buttons:
            return None

        keyboard = []
        for button_row in buttons:
            row = []
            for button in button_row:
                button_data = {
                    'text': button['text']
                }
                if button.get('url'):
                    button_data['url'] = button['url']
                if button.get('callback_data'):
                    button_data['callback_data'] = button['callback_data']

                row.append(button_data)
            keyboard.append(row)

        return {'inline_keyboard': keyboard}

    def generate_auth_code(self, user_id):
        """Генерирует уникальный код авторизации"""
        code = secrets.randbelow(900000) + 100000  # 6-значный код
        self.auth_codes[user_id] = {
            'code': str(code),
            'timestamp': time.time()
        }
        return str(code)

    def process_auth_command(self, message):
        """Обрабатывает команду /auth"""
        chat_id = message['chat']['id']
        user_id = message['from']['id']

        code = self.generate_auth_code(user_id)

        auth_text = f"""🔐 <b>Авторизация на сайте</b>

Ваш код авторизации: <code>{code}</code>

<b>Инструкция:</b>
1. Перейдите на сайт: {settings.TELEGRAM_WEB_APP_URL}
2. Войдите в свой аккаунт (или зарегистрируйтесь)
3. Перейдите в профиль → Настройки
4. Введите код: <code>{code}</code>

⏰ Код действителен 10 минут

Или используйте быструю ссылку:
{settings.TELEGRAM_WEB_APP_URL}/auth/telegram/"""

        buttons = [
            [{'text': '🌐 Открыть сайт', 'url': settings.TELEGRAM_WEB_APP_URL}],
            [{'text': '🚀 Быстрая авторизация', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/auth/telegram/"}],
        ]
        keyboard = self.create_inline_keyboard(buttons)

        self.send_message(chat_id, auth_text, keyboard)

    def process_message(self, message):
        """Обрабатывает входящее сообщение"""
        chat_id = message['chat']['id']
        text = message.get('text', '').strip()

        logger.info(f"📨 Получено сообщение от {chat_id}: {text}")

        if text.startswith('/start'):
            buttons = [
                [{'text': '🌐 Открыть сайт', 'url': settings.TELEGRAM_WEB_APP_URL}],
                [{'text': '🔐 Авторизация', 'callback_data': 'auth'}],
                [{'text': '📝 Мои статьи', 'callback_data': 'my_articles'}],
                [{'text': '🔍 Поиск статей', 'callback_data': 'search'}],
            ]
            keyboard = self.create_inline_keyboard(buttons)

            welcome_text = f"""👋 Привет, {message['chat'].get('first_name', 'друг')}!

Я бот для Форума по Вселенной Ведьмака ⚔️

<b>Команды:</b>
/start - Главное меню
/auth - Авторизация на сайте
/articles - Последние статьи
/search - Поиск статей
/profile - Мой профиль
/help - Помощь

🌐 <b>Сайт:</b> {settings.TELEGRAM_WEB_APP_URL}"""

            self.send_message(chat_id, welcome_text, keyboard)

        elif text.startswith('/auth'):
            self.process_auth_command(message)

        elif text.startswith('/help'):
            help_text = """🤖 <b>Команды бота:</b>

/start - Главное меню
/auth - Авторизация на сайте
/articles - Последние статьи  
/search <запрос> - Поиск статей
/profile - Информация о профиле
/help - Эта справка

🔐 <b>Авторизация:</b>
Используйте /auth для получения кода авторизации

🌐 <b>Веб-версия:</b>
{settings.TELEGRAM_WEB_APP_URL}"""

            self.send_message(chat_id, help_text)

        elif text.startswith('/articles'):
            try:
                recent_articles = Article.objects.filter(status='published').order_by('-created_at')[:5]

                if not recent_articles:
                    self.send_message(chat_id, "📝 Пока нет опубликованных статей.")
                    return

                articles_text = "📚 <b>Последние статьи:</b>\n\n"
                for article in recent_articles:
                    articles_text += f"• <b>{article.title}</b>\n"
                    articles_text += f"  👤 {article.author.username}\n"
                    articles_text += f"  📅 {article.created_at.strftime('%d.%m.%Y')}\n"
                    articles_text += f"  🔗 {settings.TELEGRAM_WEB_APP_URL}/article/{article.slug}/\n\n"

                buttons = [
                    [{'text': '📖 Все статьи', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/"}],
                    [{'text': '✍️ Написать статью', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/article/create/"}],
                ]
                keyboard = self.create_inline_keyboard(buttons)

                self.send_message(chat_id, articles_text, keyboard)

            except Exception as e:
                logger.error(f"Ошибка при получении статей: {e}")
                self.send_message(chat_id, "❌ Ошибка при загрузке статей")

        elif text.startswith('/search'):
            query = text.replace('/search', '').strip()

            if not query:
                self.send_message(chat_id,
                                  "🔍 <b>Использование:</b> /search &lt;запрос&gt;\n\n<b>Пример:</b> /search Геральт")
                return

            try:
                articles = Article.objects.filter(
                    Q(title__icontains=query) | Q(content__icontains=query),
                    status='published'
                )[:10]

                if not articles:
                    self.send_message(chat_id, f"❌ По запросу '{query}' ничего не найдено.")
                    return

                search_text = f"🔍 <b>Результаты поиска по '{query}':</b>\n\n"
                for article in articles:
                    search_text += f"• <b>{article.title}</b>\n"
                    search_text += f"  👤 {article.author.username}\n"
                    search_text += f"  🔗 {settings.TELEGRAM_WEB_APP_URL}/article/{article.slug}/\n\n"

                buttons = [
                    [{'text': '🌐 Расширенный поиск', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/search/?q={query}"}],
                ]
                keyboard = self.create_inline_keyboard(buttons)

                self.send_message(chat_id, search_text, keyboard)

            except Exception as e:
                logger.error(f"Ошибка при поиске: {e}")
                self.send_message(chat_id, "❌ Ошибка при поиске")

        elif text.startswith('/profile'):
            user_id = message['from']['id']

            try:
                telegram_user = TelegramUser.objects.get(telegram_id=user_id)
                django_user = telegram_user.user

                articles_count = Article.objects.filter(author=django_user, status='published').count()
                total_views = Article.objects.filter(author=django_user).aggregate(Sum('views_count'))[
                                  'views_count__sum'] or 0

                profile_text = f"""👤 <b>Ваш профиль</b>

<b>Имя:</b> {django_user.username}
<b>Статей опубликовано:</b> {articles_count}
<b>Всего просмотров:</b> {total_views}
<b>Telegram:</b> @{message['from'].get('username', 'не указан')}

<b>Ссылки:</b>
🌐 {settings.TELEGRAM_WEB_APP_URL}/user/{django_user.username}/
📝 {settings.TELEGRAM_WEB_APP_URL}/my-articles/  
✍️ {settings.TELEGRAM_WEB_APP_URL}/article/create/"""

            except TelegramUser.DoesNotExist:
                profile_text = f"""👤 <b>Вы еще не авторизованы на сайте</b>

Для доступа ко всем функциям используйте команду /auth

🌐 <b>Сайт:</b> {settings.TELEGRAM_WEB_APP_URL}/login/"""

            buttons = [
                [{'text': '🌐 Открыть сайт', 'url': settings.TELEGRAM_WEB_APP_URL}],
                [{'text': '🔐 Авторизация', 'callback_data': 'auth'}],
            ]
            keyboard = self.create_inline_keyboard(buttons)

            self.send_message(chat_id, profile_text, keyboard)

        elif text and text.startswith('/'):
            self.send_message(chat_id, "❌ Неизвестная команда. Используйте /help для списка команд.")

    def process_callback_query(self, callback_query):
        """Обрабатывает callback queries"""
        chat_id = callback_query['message']['chat']['id']
        data = callback_query['data']

        logger.info(f"🔄 Callback query: {data} от {chat_id}")

        if data == "auth":
            self.process_auth_command({'chat': {'id': chat_id}, 'from': callback_query['from']})

        elif data == "my_articles":
            user_id = callback_query['from']['id']
            try:
                telegram_user = TelegramUser.objects.get(telegram_id=user_id)
                url = f"{settings.TELEGRAM_WEB_APP_URL}/my-articles/"
                self.send_message(
                    chat_id,
                    "📝 <b>Ваши статьи</b>\n\nПерейдите по ссылке чтобы увидеть ваши статьи:",
                    self.create_inline_keyboard([[{'text': '📖 Мои статьи', 'url': url}]])
                )
            except TelegramUser.DoesNotExist:
                self.send_message(
                    chat_id,
                    "❌ <b>Вы еще не авторизованы на сайте.</b>\n\nИспользуйте команду /auth для авторизации:",
                    self.create_inline_keyboard([[{'text': '🔐 Авторизация', 'callback_data': 'auth'}]])
                )

        elif data == "search":
            self.send_message(
                chat_id,
                "🔍 <b>Поиск статей</b>\n\nИспользуйте команду /search &lt;запрос&gt;\n\n<b>Пример:</b> /search ведьмак"
            )

    def run(self):
        """Запускает бота в бесконечном цикле"""
        if not self.token:
            logger.error("❌ TELEGRAM_BOT_TOKEN не настроен в settings.py")
            return

        # Проверяем бота перед запуском
        if not self.check_bot_token():
            logger.error("❌ Не удалось подключиться к боту. Проверьте токен.")
            return

        logger.info("🤖 Синхронный Telegram бот запущен")

        while True:
            try:
                updates = self.get_updates()

                for update in updates:
                    self.last_update_id = update['update_id']

                    if 'message' in update:
                        self.process_message(update['message'])
                    elif 'callback_query' in update:
                        self.process_callback_query(update['callback_query'])

                # Очищаем устаревшие коды авторизации
                current_time = time.time()
                expired_users = [
                    user_id for user_id, auth_data in self.auth_codes.items()
                    if current_time - auth_data['timestamp'] > 600  # 10 минут
                ]
                for user_id in expired_users:
                    del self.auth_codes[user_id]

                time.sleep(0.5)

            except KeyboardInterrupt:
                logger.info("⏹️ Остановка бота")
                break
            except Exception as e:
                logger.error(f"Критическая ошибка: {e}")
                time.sleep(5)


# Глобальный экземпляр
sync_bot = SyncTelegramBot()