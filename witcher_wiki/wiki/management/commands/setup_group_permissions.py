from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.apps import apps
from wiki.permissions import GROUP_PERMISSIONS  # Импортируем ТВОЙ файл


class Command(BaseCommand):
    help = 'Настраивает права для групп пользователей используя permissions.py'

    def handle(self, *args, **options):
        self.stdout.write('🚀 Настройка прав для групп пользователей...')

        for group_name, group_config in GROUP_PERMISSIONS.items():
            # Создаем или получаем группу
            group, created = Group.objects.get_or_create(name=group_name)

            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Создана группа: {group_name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'🔄 Обновляем группу: {group_name}')
                )

            # Очищаем текущие права группы
            group.permissions.clear()

            # Добавляем технические права на модели
            model_permissions_added = 0
            technical_permissions = group_config.get('technical_permissions', {})

            for model_name, permissions in technical_permissions.items():
                try:
                    # Получаем ContentType для модели
                    model_class = apps.get_model('wiki', model_name)
                    content_type = ContentType.objects.get_for_model(model_class)

                    # Получаем и добавляем права
                    for perm in permissions:
                        codename = f'{perm}_{model_name}'
                        try:
                            permission = Permission.objects.get(
                                content_type=content_type,
                                codename=codename
                            )
                            group.permissions.add(permission)
                            model_permissions_added += 1
                        except Permission.DoesNotExist:
                            self.stdout.write(
                                self.style.WARNING(f'⚠️ Право не найдено: {codename}')
                            )

                except LookupError:
                    self.stdout.write(
                        self.style.ERROR(f'❌ Модель не найдена: {model_name}')
                    )

            # Добавляем кастомные права (из модели Article)
            custom_permissions_added = 0
            article_content_type = ContentType.objects.get_for_model(
                apps.get_model('wiki', 'Article')
            )

            custom_permissions = group_config.get('custom_permissions', [])
            for perm_codename in custom_permissions:
                try:
                    # Ищем кастомное право
                    permission = Permission.objects.get(
                        content_type=article_content_type,
                        codename=perm_codename
                    )
                    group.permissions.add(permission)
                    custom_permissions_added += 1
                except Permission.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️ Кастомное право не найдено: {perm_codename}')
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Группа "{group_name}": {model_permissions_added} прав на модели, '
                    f'{custom_permissions_added} кастомных прав'
                )
            )

        self.stdout.write(
            self.style.SUCCESS('🎉 Настройка прав групп завершена!')
        )