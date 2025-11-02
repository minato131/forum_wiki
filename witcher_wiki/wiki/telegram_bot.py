import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q, Sum

# Исправленный импорт
from .models import TelegramUser, Article

logger = logging.getLogger(__name__)


class WitcherWikiBot:
    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.application = None

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        keyboard = [
            [InlineKeyboardButton("🌐 Открыть сайт", url=settings.TELEGRAM_WEB_APP_URL)],
            [InlineKeyboardButton("📝 Мои статьи", callback_data="my_articles")],
            [InlineKeyboardButton("🔍 Поиск статей", callback_data="search")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        welcome_text = f"""
👋 Привет, {user.first_name}!

Я бот для Форума по Вселенной Ведьмака ⚔️

Здесь ты можешь:
• 📖 Читать статьи о мире Ведьмака
• ✍️ Писать собственные статьи
• 🔍 Искать информацию по персонажам, монстрам и локациям
• 💬 Обсуждать с другими фанатами

Используй кнопки ниже или команды:
/start - Главное меню
/articles - Последние статьи
/search - Поиск статей
/profile - Мой профиль
/help - Помощь
        """

        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
🤖 *Команды бота:*

*/start* - Главное меню
*/articles* - Последние опубликованные статьи
*/search <запрос>* - Поиск статей
*/profile* - Информация о профиле
*/help* - Эта справка

🌐 *Веб-версия:*
Для полного доступа ко всем функциям используйте веб-версию сайта.
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def articles_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает последние статьи"""
        recent_articles = Article.objects.filter(status='published').order_by('-created_at')[:5]

        if not recent_articles:
            await update.message.reply_text("📝 Пока нет опубликованных статей.")
            return

        articles_text = "📚 *Последние статьи:*\n\n"
        for article in recent_articles:
            articles_text += f"• *{article.title}*\n"
            articles_text += f"  👤 {article.author.username}\n"
            articles_text += f"  📅 {article.created_at.strftime('%d.%m.%Y')}\n"
            articles_text += f"  🔗 [Читать]({settings.TELEGRAM_WEB_APP_URL}/article/{article.slug}/)\n\n"

        keyboard = [
            [InlineKeyboardButton("📖 Все статьи", url=f"{settings.TELEGRAM_WEB_APP_URL}/")],
            [InlineKeyboardButton("✍️ Написать статью", url=f"{settings.TELEGRAM_WEB_APP_URL}/article/create/")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(articles_text, parse_mode='Markdown', reply_markup=reply_markup)

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Поиск статей"""
        query = ' '.join(context.args)

        if not query:
            await update.message.reply_text("🔍 *Использование:* /search <запрос>\n\nПример: /search Геральт")
            return

        articles = Article.objects.filter(
            Q(title__icontains=query) | Q(content__icontains=query),
            status='published'
        )[:10]

        if not articles:
            await update.message.reply_text(f"❌ По запросу '{query}' ничего не найдено.")
            return

        search_text = f"🔍 *Результаты поиска по '{query}':*\n\n"
        for article in articles:
            search_text += f"• *{article.title}*\n"
            search_text += f"  👤 {article.author.username}\n"
            search_text += f"  🔗 [Читать]({settings.TELEGRAM_WEB_APP_URL}/article/{article.slug}/)\n\n"

        keyboard = [
            [InlineKeyboardButton("🌐 Расширенный поиск", url=f"{settings.TELEGRAM_WEB_APP_URL}/search/?q={query}")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(search_text, parse_mode='Markdown', reply_markup=reply_markup)

    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Информация о профиле пользователя"""
        user = update.effective_user

        try:
            # Ищем пользователя в нашей базе
            telegram_user = TelegramUser.objects.get(telegram_id=user.id)
            django_user = telegram_user.user

            # Статистика пользователя
            articles_count = Article.objects.filter(author=django_user, status='published').count()
            total_views = Article.objects.filter(author=django_user).aggregate(Sum('views_count'))[
                              'views_count__sum'] or 0

            profile_text = f"""
👤 *Ваш профиль:*

*Имя:* {django_user.username}
*Статей опубликовано:* {articles_count}
*Всего просмотров:* {total_views}
*Telegram:* @{user.username or 'не указан'}

*Ссылки:*
🌐 [Мой профиль на сайте]({settings.TELEGRAM_WEB_APP_URL}/user/{django_user.username}/)
📝 [Мои статьи]({settings.TELEGRAM_WEB_APP_URL}/my-articles/)
✍️ [Написать статью]({settings.TELEGRAM_WEB_APP_URL}/article/create/)
            """

        except TelegramUser.DoesNotExist:
            profile_text = f"""
👤 *Вы еще не зарегистрированы на сайте*

Для доступа ко всем функциям:
1. Нажмите кнопку ниже
2. Авторизуйтесь через Telegram
3. Начните писать статьи!

🌐 [Зарегистрироваться]({settings.TELEGRAM_WEB_APP_URL}/login/)
            """

        keyboard = [
            [InlineKeyboardButton("🌐 Открыть сайт", url=settings.TELEGRAM_WEB_APP_URL)],
            [InlineKeyboardButton("📝 Мои статьи", callback_data="my_articles")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(profile_text, parse_mode='Markdown', reply_markup=reply_markup)

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()

        if query.data == "my_articles":
            user = query.from_user
            try:
                telegram_user = TelegramUser.objects.get(telegram_id=user.id)
                url = f"{settings.TELEGRAM_WEB_APP_URL}/my-articles/"
                await query.edit_message_text(
                    f"📝 *Ваши статьи*\n\nПерейдите по ссылке чтобы увидеть ваши статьи:",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📖 Мои статьи", url=url)]])
                )
            except TelegramUser.DoesNotExist:
                await query.edit_message_text(
                    "❌ Вы еще не авторизованы на сайте.\n\nНажмите кнопку ниже чтобы войти:",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🌐 Войти", url=f"{settings.TELEGRAM_WEB_APP_URL}/login/")]])
                )

        elif query.data == "search":
            await query.edit_message_text(
                "🔍 *Поиск статей*\n\nИспользуйте команду /search <запрос>\n\nПример: /search ведьмак",
                parse_mode='Markdown'
            )

    def setup_handlers(self):
        """Настройка обработчиков команд"""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("articles", self.articles_command))
        self.application.add_handler(CommandHandler("search", self.search_command))
        self.application.add_handler(CommandHandler("profile", self.profile_command))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))

    async def run(self):
        """Запуск бота"""
        self.application = Application.builder().token(self.token).build()
        self.setup_handlers()

        logger.info("🤖 Telegram бот запущен")
        await self.application.run_polling()


# Глобальный экземпляр бота
bot = WitcherWikiBot()