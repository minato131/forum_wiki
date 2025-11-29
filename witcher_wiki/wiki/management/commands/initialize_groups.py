from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from wiki.models import Article, Category, Comment
from wiki.permissions import GROUP_PERMISSIONS


class Command(BaseCommand):
    help = 'Инициализирует группы пользователей с соответствующими правами'

    def handle(self, *args, **options):
        # Создаем группы если их нет
        for group_name in GROUP_PERMISSIONS.keys():
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Создана группа: {group_name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠️ Группа уже существует: {group_name}')
                )

        # Назначаем права для Модератора
        moderator_group = Group.objects.get(name='Модератор')
        moderator_permissions = [
            'can_moderate',  # из модели Article
            'can_manage_categories',  # из модели Article
            'delete_comment',  # предполагаемое право
        ]

        # Добавляем права на модерацию статей
        article_content_type = ContentType.objects.get_for_model(Article)
        moderator_perms = Permission.objects.filter(
            content_type=article_content_type,
            codename__in=['can_moderate', 'can_manage_categories']
        )
        moderator_group.permissions.add(*moderator_perms)

        self.stdout.write(
            self.style.SUCCESS('✅ Права для групп инициализированы')
        )