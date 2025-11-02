import os
import django
import logging
import requests
import time
import json
from django.conf import settings
from django.db.models import Q, Sum

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'witcher_wiki.settings')
django.setup()

from wiki.models import TelegramUser, Article

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

    def process_message(self, message):
        """Обрабатывает входящее сообщение"""
        chat_id = message['chat']['id']
        text = message.get('text', '').strip()

        logger.info(f"📨 Получено сообщение от {chat_id}: {text}")

        if text.startswith('/start'):
            buttons = [
                [{'text': '🌐 Открыть сайт', 'url': settings.TELEGRAM_WEB_APP_URL}],
                [{'text': '📝 Мои статьи', 'callback_data': 'my_articles'}],
                [{'text': '🔍 Поиск статей', 'callback_data': 'search'}],
            ]
            keyboard = self.create_inline_keyboard(buttons)

            welcome_text = f"""👋 Привет, {message['chat'].get('first_name', 'друг')}!

Я бот для Форума по Вселенной Ведьмака ⚔️

Команды:
/start - Главное меню
/articles - Последние статьи
/search - Поиск статей
/profile - Мой профиль
/help - Помощь"""

            self.send_message(chat_id, welcome_text, keyboard)

        elif text.startswith('/help'):
            help_text = """🤖 Команды бота:

/start - Главное меню
/articles - Последние статьи  
/search <запрос> - Поиск статей
/profile - Информация о профиле
/help - Эта справка

🌐 Веб-версия:
Для полного доступа ко всем функциям используйте веб-версию сайта."""

            self.send_message(chat_id, help_text)

        elif text.startswith('/articles'):
            try:
                recent_articles = Article.objects.filter(status='published').order_by('-created_at')[:5]

                if not recent_articles:
                    self.send_message(chat_id, "📝 Пока нет опубликованных статей.")
                    return

                articles_text = "📚 Последние статьи:\n\n"
                for article in recent_articles:
                    articles_text += f"• {article.title}\n"
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
                self.send_message(chat_id, "🔍 Использование: /search <запрос>\n\nПример: /search Геральт")
                return

            try:
                articles = Article.objects.filter(
                    Q(title__icontains=query) | Q(content__icontains=query),
                    status='published'
                )[:10]

                if not articles:
                    self.send_message(chat_id, f"❌ По запросу '{query}' ничего не найдено.")
                    return

                search_text = f"🔍 Результаты поиска по '{query}':\n\n"
                for article in articles:
                    search_text += f"• {article.title}\n"
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

                profile_text = f"""👤 Ваш профиль:

Имя: {django_user.username}
Статей опубликовано: {articles_count}
Всего просмотров: {total_views}
Telegram: @{message['from'].get('username', 'не указан')}

Ссылки:
🌐 {settings.TELEGRAM_WEB_APP_URL}/user/{django_user.username}/
📝 {settings.TELEGRAM_WEB_APP_URL}/my-articles/  
✍️ {settings.TELEGRAM_WEB_APP_URL}/article/create/"""

            except TelegramUser.DoesNotExist:
                profile_text = f"""👤 Вы еще не зарегистрированы на сайте

Для доступа ко всем функциям:
🌐 {settings.TELEGRAM_WEB_APP_URL}/login/"""

            buttons = [
                [{'text': '🌐 Открыть сайт', 'url': settings.TELEGRAM_WEB_APP_URL}],
                [{'text': '📝 Мои статьи', 'callback_data': 'my_articles'}],
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

        if data == "my_articles":
            user_id = callback_query['from']['id']
            try:
                telegram_user = TelegramUser.objects.get(telegram_id=user_id)
                url = f"{settings.TELEGRAM_WEB_APP_URL}/my-articles/"
                self.send_message(
                    chat_id,
                    "📝 Ваши статьи\n\nПерейдите по ссылке чтобы увидеть ваши статьи:",
                    self.create_inline_keyboard([[{'text': '📖 Мои статьи', 'url': url}]])
                )
            except TelegramUser.DoesNotExist:
                self.send_message(
                    chat_id,
                    "❌ Вы еще не авторизованы на сайте.\n\nНажмите кнопку ниже чтобы войти:",
                    self.create_inline_keyboard(
                        [[{'text': '🌐 Войти', 'url': f"{settings.TELEGRAM_WEB_APP_URL}/login/"}]])
                )

        elif data == "search":
            self.send_message(
                chat_id,
                "🔍 Поиск статей\n\nИспользуйте команду /search <запрос>\n\nПример: /search ведьмак"
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

                time.sleep(0.5)

            except KeyboardInterrupt:
                logger.info("⏹️ Остановка бота")
                break
            except Exception as e:
                logger.error(f"Критическая ошибка: {e}")
                time.sleep(5)


# Глобальный экземпляр
sync_bot = SyncTelegramBot()