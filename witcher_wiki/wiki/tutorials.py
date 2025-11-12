from .models import UserTutorial
from django.utils import timezone


class TutorialManager:
    """Менеджер системы подсказок"""

    TUTORIALS = {
        'welcome': {
            'title': '👋 Добро пожаловать в Энциклопедию Ведьмака!',
            'content': '''
                <p>Мы рады приветствовать вас в нашем сообществе! Здесь вы найдете:</p>
                <ul>
                    <li>📚 Статьи о персонажах, монстрах и локациях мира Ведьмака</li>
                    <li>✍️ Возможность создавать собственные статьи</li>
                    <li>💬 Обсуждения с другими фанатами</li>
                    <li>🔍 Умный поиск по хештегам и категориям</li>
                </ul>
                <p>Давайте начнем знакомство с основными функциями!</p>
            ''',
            'position': 'center',
            'next_tutorial': 'navigation'
        },
        'navigation': {
            'title': '🧭 Навигация по сайту',
            'content': '''
                <p>Основные разделы сайта:</p>
                <ul>
                    <li><strong>Главная</strong> - популярные статьи и категории</li>
                    <li><strong>Поиск</strong> - находите статьи по ключевым словам и хештегам</li>
                    <li><strong>Создать статью</strong> - добавляйте собственные материалы</li>
                    <li><strong>Профиль</strong> - управляйте своими настройками</li>
                </ul>
            ''',
            'position': 'bottom-right',
            'next_tutorial': 'article_creation'
        },
        'article_creation': {
            'title': '✍️ Создание статей',
            'content': '''
                <p>Вы можете создавать собственные статьи!</p>
                <ul>
                    <li>📝 Используйте богатый текстовый редактор</li>
                    <li>🏷️ Добавляйте хештеги для лучшего поиска</li>
                    <li>📁 Выбирайте подходящие категории</li>
                    <li>🖼️ Загружайте изображения и медиафайлы</li>
                </ul>
                <p>Все статьи проходят модерацию перед публикацией.</p>
            ''',
            'position': 'bottom-left',
            'next_tutorial': 'search_tips'
        },
        'search_tips': {
            'title': '🔍 Советы по поиску',
            'content': '''
                <p>Используйте мощный поиск для нахождения нужных статей:</p>
                <ul>
                    <li>🔤 Ищите по названию, содержанию или хештегам</li>
                    <li>📁 Фильтруйте по категориям</li>
                    <li>🏷️ Кликайте на хештеги для быстрого поиска</li>
                    <li>📊 Смотрите популярные запросы и теги</li>
                </ul>
            ''',
            'position': 'top-right',
            'next_tutorial': 'completion'
        },
        'completion': {
            'title': '🎉 Обучение завершено!',
            'content': '''
                <p>Теперь вы знаете основные возможности нашей энциклопедии!</p>
                <p>Если у вас остались вопросы:</p>
                <ul>
                    <li>📖 Читайте раздел помощи</li>
                    <li>💬 Задавайте вопросы в комментариях</li>
                    <li>📧 Обращайтесь в поддержку</li>
                </ul>
                <p>Приятного использования!</p>
            ''',
            'position': 'center',
            'next_tutorial': None
        }
    }

    @classmethod
    def get_next_tutorial(cls, user):
        """Получить следующую непросмотренную подсказку для пользователя"""
        if not user.is_authenticated:
            return None

        # Проверяем все подсказки по порядку
        for tutorial_key in cls.TUTORIALS.keys():
            tutorial, created = UserTutorial.objects.get_or_create(
                user=user,
                tutorial_key=tutorial_key
            )
            if not tutorial.is_completed:
                return tutorial_key

        return None

    @classmethod
    def get_tutorial_data(cls, tutorial_key):
        """Получить данные подсказки по ключу"""
        return cls.TUTORIALS.get(tutorial_key)

    @classmethod
    def mark_tutorial_completed(cls, user, tutorial_key):
        """Пометить подсказку как просмотренную"""
        if not user.is_authenticated:
            return False

        try:
            tutorial = UserTutorial.objects.get(user=user, tutorial_key=tutorial_key)
            tutorial.mark_as_completed()
            return True
        except UserTutorial.DoesNotExist:
            return False

    @classmethod
    def reset_tutorials(cls, user):
        """Сбросить все подсказки для пользователя"""
        if not user.is_authenticated:
            return False

        UserTutorial.objects.filter(user=user).update(
            is_completed=False,
            completed_at=None
        )
        return True

    @classmethod
    def get_progress(cls, user):
        """Получить прогресс обучения пользователя"""
        if not user.is_authenticated:
            return 0

        total = len(cls.TUTORIALS)
        completed = UserTutorial.objects.filter(user=user, is_completed=True).count()

        return int((completed / total) * 100) if total > 0 else 0