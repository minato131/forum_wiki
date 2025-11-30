from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from wiki.logging_utils import ActionLogger
from django.test import RequestFactory


class Command(BaseCommand):
    help = 'Генерация тестовых логов для проверки системы'

    def handle(self, *args, **options):
        self.stdout.write("🧪 Генерация тестовых логов...")

        # Создаем тестовый запрос
        factory = RequestFactory()
        request = factory.get('/test/')

        # Получаем или создаем тестового пользователя
        user, created = User.objects.get_or_create(
            username='test_user',
            defaults={'email': 'test@example.com', 'password': 'testpass123'}
        )
        request.user = user

        # Генерируем тестовые логи
        test_actions = [
            ('login', 'Вход в систему'),
            ('article_view', 'Просмотр статьи'),
            ('article_create', 'Создание статьи'),
            ('search', 'Поиск по сайту'),
            ('profile_view', 'Просмотр профиля'),
            ('logout', 'Выход из системы'),
        ]

        for action_type, description in test_actions:
            ActionLogger.log_action(
                request=request,
                action_type=action_type,
                description=f'ТЕСТ: {description}',
                extra_data={'test_data': True}
            )
            self.stdout.write(f"✅ Создан лог: {action_type}")

        self.stdout.write(
            self.style.SUCCESS("✅ Тестовые логи успешно созданы!")
        )