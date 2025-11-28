import os
import django
import logging
import requests
import time
import json
import secrets
from django.conf import settings
from django.db.models import Q, Sum
from django.contrib.auth import login as auth_login
from django.contrib.auth.models import User

# Настройка Django ДО импорта моделей
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'witcher_wiki.settings')
django.setup()

from wiki.models import TelegramUser, Article, UserProfile, AuthCode, TelegramLoginToken
from wiki.telegram_utils import TelegramAuth

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

            response = requests.post(url, json=data, timeout=10)

            if response.status_code == 400:
                # Bad Request - попробуем без HTML разметки
                logger.warning("❌ Ошибка 400, пробуем без HTML...")
                data['parse_mode'] = None
                response = requests.post(url, json=data, timeout=10)

            response.raise_for_status()
            return True

        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP ошибка при отправке сообщения: {e}")
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

    def create_reply_keyboard(self, buttons, resize_keyboard=True, one_time_keyboard=False):
        """Создает reply клавиатуру"""
        keyboard = []
        for button_row in buttons:
            row = []
            for button in button_row:
                row.append({'text': button})
            keyboard.append(row)

        return {
            'keyboard': keyboard,
            'resize_keyboard': resize_keyboard,
            'one_time_keyboard': one_time_keyboard
        }

    def generate_auth_code(self, user_id, username='', first_name=''):
        """Генерирует уникальный код авторизации"""
        code = secrets.randbelow(900000) + 100000  # 6-значный код

        # Сохраняем код в базу данных
        auth_code = AuthCode.objects.create(
            code=str(code),
            telegram_id=user_id,
            telegram_username=username,
            first_name=first_name,
            expires_at=time.time() + 600  # 10 минут
        )

        return str(code)

    def process_start_command(self, message, args=None):
        """Обрабатывает команду /start с аргументами"""
        chat_id = message['chat']['id']
        user_id = message['from']['id']
        username = message['from'].get('username', '')
        first_name = message['from'].get('first_name', '')

        # Проверяем аргументы команды
        if args:
            if args[0] == 'auth':
                self.process_auth_command(message)
                return
            elif args[0] == 'login':
                self.process_login_command(message)
                return
            elif args[0].startswith('article_'):
                article_slug = args[0].replace('article_', '')
                self.process_article_share(message, article_slug)
                return

        # Стандартное приветствие
        welcome_text = f"""👋 Привет, {first_name}!

Я бот для Форума по Вселенной Ведьмака ⚔️

С моей помощью ты можешь:
• 🔐 Быстро авторизоваться на сайте
• 📝 Создавать и редактировать статьи  
• 🔍 Искать информацию по вселенной
• 📚 Читать статьи прямо в Telegram
• 🔔 Получать уведомления о новых материалах

<b>Основные команды:</b>
/start - Главное меню
/auth - Авторизация на сайте
/login - Быстрый вход
/profile - Мой профиль
/articles - Последние статьи
/search - Поиск статей
/help - Помощь

🌐 <b>Сайт:</b> {settings.TELEGRAM_WEB_APP_URL}"""

        buttons = [
            [
                {'text': '🔐 Авторизация', 'callback_data': 'auth'},
                {'text': '📝 Мои статьи', 'callback_data': 'my_articles'}
            ],
            [
                {'text': '🌐 Открыть сайт', 'url': settings.TELEGRAM_WEB_APP_URL},
                {'text': '🔍 Поиск', 'callback_data': 'search'}
            ],
            [
                {'text': '📚 Все статьи', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/"},
                {'text': '✍️ Новая статья', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/article/create/"}
            ]
        ]
        keyboard = self.create_inline_keyboard(buttons)

        self.send_message(chat_id, welcome_text, keyboard)

    def process_auth_command(self, message):
        """Обрабатывает команду /auth - привязка аккаунта"""
        chat_id = message['chat']['id']
        user_id = message['from']['id']
        username = message['from'].get('username', '')
        first_name = message['from'].get('first_name', '')

        # Проверяем, не привязан ли уже аккаунт
        try:
            telegram_user = TelegramUser.objects.get(telegram_id=user_id)
            # Аккаунт уже привязан
            auth_text = f"""✅ <b>Аккаунт уже привязан</b>

Ваш Telegram аккаунт уже привязан к пользователю:
<b>Имя:</b> {telegram_user.user.username}
<b>Email:</b> {telegram_user.user.email}

Для входа на сайт используйте команду /login"""

            buttons = [
                [{'text': '🚀 Быстрый вход', 'callback_data': 'quick_login'}],
                [{'text': '🌐 Открыть сайт', 'url': settings.TELEGRAM_WEB_APP_URL}],
                [{'text': '📝 Мои статьи', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/my-articles/"}]
            ]
            keyboard = self.create_inline_keyboard(buttons)

        except TelegramUser.DoesNotExist:
            # Генерируем код для привязки
            code = self.generate_auth_code(user_id, username, first_name)

            auth_text = f"""🔐 <b>Привязка аккаунта</b>

Ваш код привязки: <code>{code}</code>

<b>Инструкция:</b>
1. Перейдите на сайт: {settings.TELEGRAM_WEB_APP_URL}
2. Войдите в свой аккаунт (или зарегистрируйтесь)
3. Перейдите в профиль → Настройки
4. Введите код: <code>{code}</code>

⏰ Код действителен 10 минут

<b>Или используйте быстрые ссылки:</b>"""

            buttons = [
                [{'text': '🌐 Открыть сайт', 'url': settings.TELEGRAM_WEB_APP_URL}],
                [{'text': '🚀 Ввести код', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/auth/telegram/code/"}],
                [{'text': '📝 Регистрация', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/register/"}],
                [{'text': '🔐 Войти', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/login/"}]
            ]
            keyboard = self.create_inline_keyboard(buttons)

        self.send_message(chat_id, auth_text, keyboard)

    def process_login_command(self, message):
        """Обрабатывает команду /login - быстрый вход"""
        chat_id = message['chat']['id']
        user_id = message['from']['id']
        username = message['from'].get('username', '')
        first_name = message['from'].get('first_name', '')

        try:
            telegram_user = TelegramUser.objects.get(telegram_id=user_id)
            django_user = telegram_user.user

            # Простая ссылка с telegram_id
            login_url = f"{settings.TELEGRAM_WEB_APP_URL}/auth/telegram/quick/?tg_id={user_id}"

            login_text = f"""🚀 <b>Быстрый вход</b>

    Для входа на сайт используйте ссылку ниже.
    Вы будете автоматически авторизованы как:
    <b>{django_user.username}</b>

    Нажмите кнопку 👇"""

            buttons = [
                [{'text': '🚀 Войти на сайт', 'url': login_url}],
                [{'text': '📝 Мои статьи', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/my-articles/"}],
                [{'text': '✍️ Новая статья', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/article/create/"}]
            ]
            keyboard = self.create_inline_keyboard(buttons)

            self.send_message(chat_id, login_text, keyboard)

        except TelegramUser.DoesNotExist:
            # Аккаунт не привязан
            self.send_message(
                chat_id,
                f"""❌ <b>Аккаунт не привязан</b>

    Сначала привяжите ваш Telegram аккаунт.

    1. Используйте команду /auth
    2. Получите код привязки
    3. Введите код на сайте в настройках профиля

    Или зарегистрируйтесь на сайте и привяжите аккаунт.""",
                self.create_inline_keyboard([
                    [{'text': '🔐 Привязать аккаунт', 'callback_data': 'auth'}],
                    [{'text': '🌐 Открыть сайт', 'url': settings.TELEGRAM_WEB_APP_URL}]
                ])
            )

    def process_articles_command(self, message):
        """Обрабатывает команду /articles"""
        chat_id = message['chat']['id']
        user_id = message['from']['id']

        try:
            recent_articles = Article.objects.filter(status='published').order_by('-created_at')[:5]

            if not recent_articles:
                self.send_message(chat_id, "📝 <b>Пока нет опубликованных статей.</b>")
                return

            articles_text = "📚 <b>Последние статьи:</b>\n\n"
            buttons = []

            for article in recent_articles:
                articles_text += f"• <b>{article.title}</b>\n"
                articles_text += f"  👤 {article.author.username}\n"
                articles_text += f"  📅 {article.created_at.strftime('%d.%m.%Y')}\n"
                articles_text += f"  👁️ {article.views_count} просмотров\n"
                articles_text += f"  ❤️ {article.get_likes_count()} лайков\n\n"

                buttons.append([{
                    'text': f"📖 {article.title[:20]}...",
                    'url': f"{settings.TELEGRAM_WEB_APP_URL}/article/{article.slug}/"
                }])

            buttons.extend([
                [{'text': '🌐 Все статьи', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/"}],
                [{'text': '🔍 Расширенный поиск', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/search/"}]
            ])

            keyboard = self.create_inline_keyboard(buttons)
            self.send_message(chat_id, articles_text, keyboard)

        except Exception as e:
            logger.error(f"Ошибка при получении статей: {e}")
            self.send_message(chat_id, "❌ Ошибка при загрузке статей")

    def process_search_command(self, message):
        """Обрабатывает команду /search"""
        chat_id = message['chat']['id']
        text = message.get('text', '').strip()
        query = text.replace('/search', '').strip()

        if not query:
            self.send_message(
                chat_id,
                "🔍 <b>Поиск статей</b>\n\nИспользуйте: /search &lt;запрос&gt;\n\n<b>Примеры:</b>\n/search Геральт\n/search ведьмак\n/search магия",
                self.create_inline_keyboard(
                    [[{'text': '🌐 Расширенный поиск', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/search/"}]])
            )
            return

        try:
            articles = Article.objects.filter(
                Q(title__icontains=query) | Q(content__icontains=query) | Q(tags__name__icontains=query),
                status='published'
            ).distinct()[:10]

            if not articles:
                self.send_message(
                    chat_id,
                    f"❌ По запросу '<b>{query}</b>' ничего не найдено.",
                    self.create_inline_keyboard([[{'text': '🔍 Новый поиск', 'callback_data': 'search'}]])
                )
                return

            search_text = f"🔍 <b>Результаты поиска по '{query}':</b>\n\n"
            buttons = []

            for article in articles:
                search_text += f"• <b>{article.title}</b>\n"
                search_text += f"  👤 {article.author.username}\n"
                search_text += f"  📅 {article.created_at.strftime('%d.%m.%Y')}\n\n"

                buttons.append([{
                    'text': f"📖 {article.title[:30]}...",
                    'url': f"{settings.TELEGRAM_WEB_APP_URL}/article/{article.slug}/"
                }])

            buttons.append([{'text': '🌐 Все результаты', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/search/?q={query}"}])

            keyboard = self.create_inline_keyboard(buttons)
            self.send_message(chat_id, search_text, keyboard)

        except Exception as e:
            logger.error(f"Ошибка при поиске: {e}")
            self.send_message(chat_id, "❌ Ошибка при поиске")

    def process_help_command(self, message):
        """Обрабатывает команду /help"""
        chat_id = message['chat']['id']

        help_text = """🤖 <b>Команды бота:</b>

<b>Основные команды:</b>
/start - Главное меню
/auth - Привязка аккаунта
/login - Быстрый вход на сайт
/profile - Информация о профиле
/articles - Последние статьи
/search - Поиск статей
/help - Эта справка

<b>Авторизация:</b>
1. Используйте /auth для привязки аккаунта
2. Получите код и введите его на сайте
3. Используйте /login для быстрого входа

<b>Работа со статьями:</b>
• Читайте статьи прямо в боте
• Переходите на сайт для создания и редактирования
• Получайте уведомления о новых материалах

🌐 <b>Веб-сайт:</b> {settings.TELEGRAM_WEB_APP_URL}

<b>Поддержка:</b>
Если возникли проблемы, обратитесь к администраторам."""

        buttons = [
            [{'text': '🌐 Открыть сайт', 'url': settings.TELEGRAM_WEB_APP_URL}],
            [{'text': '🔐 Авторизация', 'callback_data': 'auth'}],
            [{'text': '📚 Все статьи', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/"}]
        ]
        keyboard = self.create_inline_keyboard(buttons)

        self.send_message(chat_id, help_text, keyboard)

    def process_message(self, message):
        """Обрабатывает входящее сообщение"""
        chat_id = message['chat']['id']
        text = message.get('text', '').strip()

        logger.info(f"📨 Получено сообщение от {chat_id}: {text}")

        if text.startswith('/start'):
            args = text.split()[1:] if len(text.split()) > 1 else None
            self.process_start_command(message, args)

        elif text.startswith('/auth'):
            self.process_auth_command(message)

        elif text.startswith('/login'):
            self.process_login_command(message)

        elif text.startswith('/profile'):
            self.process_profile_command(message)

        elif text.startswith('/articles'):
            self.process_articles_command(message)

        elif text.startswith('/search'):
            self.process_search_command(message)

        elif text.startswith('/help'):
            self.process_help_command(message)

        elif text and text.startswith('/'):
            self.send_message(
                chat_id,
                "❌ Неизвестная команда. Используйте /help для списка команд.",
                self.create_inline_keyboard([[{'text': '📋 Справка', 'callback_data': 'help'}]])
            )

    def process_callback_query(self, callback_query):
        """Обрабатывает callback queries"""
        chat_id = callback_query['message']['chat']['id']
        data = callback_query['data']
        user_id = callback_query['from']['id']

        logger.info(f"🔄 Callback query: {data} от {chat_id}")

        if data == "auth":
            self.process_auth_command({'chat': {'id': chat_id}, 'from': callback_query['from']})

        elif data == "quick_login":
            self.process_login_command({'chat': {'id': chat_id}, 'from': callback_query['from']})

        elif data == "profile":
            self.process_profile_command({'chat': {'id': chat_id}, 'from': callback_query['from']})

        elif data == "my_articles":
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
                    "❌ <b>Аккаунт не привязан</b>\n\nСначала привяжите ваш Telegram аккаунт:",
                    self.create_inline_keyboard([[{'text': '🔐 Привязать аккаунт', 'callback_data': 'auth'}]])
                )

        elif data == "search":
            self.send_message(
                chat_id,
                "🔍 <b>Поиск статей</b>\n\nИспользуйте команду /search &lt;запрос&gt;\n\n<b>Пример:</b> /search ведьмак",
                self.create_inline_keyboard(
                    [[{'text': '🌐 Расширенный поиск', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/search/"}]])
            )

        elif data == "help":
            self.process_help_command({'chat': {'id': chat_id}, 'from': callback_query['from']})

        elif data == "articles":
            self.process_articles_command({'chat': {'id': chat_id}, 'from': callback_query['from']})

    def process_article_share(self, message, article_slug):
        """Обрабатывает шаринг статьи"""
        chat_id = message['chat']['id']


        try:
            article = Article.objects.get(slug=article_slug, status='published')

            article_text = f"""📖 <b>{article.title}</b>

{article.excerpt or article.content[:200] + '...'}

<b>Автор:</b> {article.author.username}
<b>Дата:</b> {article.created_at.strftime('%d.%m.%Y')}
<b>Просмотры:</b> {article.views_count}
<b>Лайки:</b> {article.get_likes_count()}"""

            buttons = [
                [{'text': '📖 Читать на сайте', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/article/{article.slug}/"}],
                [{'text': '👤 Профиль автора',
                  'url': f"{settings.TELEGRAM_WEB_APP_URL}/user/{article.author.username}/"}],
                [{'text': '📚 Все статьи', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/"}]
            ]
            keyboard = self.create_inline_keyboard(buttons)

            self.send_message(chat_id, article_text, keyboard)

        except Article.DoesNotExist:
            self.send_message(chat_id, "❌ Статья не найдена или не опубликована.")

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

                # Очищаем устаревшие коды авторизации и токены
                import time
                AuthCode.objects.filter(expires_at__lt=time.time()).delete()

                # Очищаем устаревшие токены входа
                from django.utils import timezone
                TelegramLoginToken.objects.filter(expires_at__lt=timezone.now()).delete()

                time.sleep(0.5)

            except KeyboardInterrupt:
                logger.info("⏹️ Остановка бота")
                break
            except Exception as e:
                logger.error(f"Критическая ошибка: {e}")
                time.sleep(5)

# Глобальный экземпляр
sync_bot = SyncTelegramBot()