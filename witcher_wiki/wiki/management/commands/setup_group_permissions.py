from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.apps import apps
from wiki.permissions import GROUP_PERMISSIONS


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

            # Добавляем права по приложению и модели
            permissions_added = []

            # 1. Добавляем права на модели через technical_permissions
            technical_permissions = group_config.get('technical_permissions', {})

            for model_name, perm_codenames in technical_permissions.items():
                try:
                    # Получаем модель
                    model_class = apps.get_model('wiki', model_name)
                    content_type = ContentType.objects.get_for_model(model_class)

                    for perm_codename in perm_codenames:
                        # Для стандартных прав (view, add, change, delete)
                        if perm_codename in ['view', 'add', 'change', 'delete']:
                            full_codename = f'{perm_codename}_{model_name}'
                        else:
                            # Для кастомных прав
                            full_codename = perm_codename

                        try:
                            permission = Permission.objects.get(
                                content_type=content_type,
                                codename=full_codename
                            )
                            group.permissions.add(permission)
                            permissions_added.append(full_codename)
                        except Permission.DoesNotExist:
                            self.stdout.write(
                                self.style.WARNING(f'⚠️ Право не найдено: {full_codename} для {model_name}')
                            )

                except LookupError:
                    self.stdout.write(
                        self.style.ERROR(f'❌ Модель не найдена: {model_name}')
                    )

            # 2. Добавляем кастомные права из Article (если они не были добавлены выше)
            custom_permissions = group_config.get('custom_permissions', [])

            if custom_permissions:
                try:
                    article_model = apps.get_model('wiki', 'Article')
                    article_content_type = ContentType.objects.get_for_model(article_model)

                    for perm_codename in custom_permissions:
                        # Проверяем, не добавили ли уже это право
                        if perm_codename not in permissions_added:
                            try:
                                permission = Permission.objects.get(
                                    content_type=article_content_type,
                                    codename=perm_codename
                                )
                                group.permissions.add(permission)
                                permissions_added.append(perm_codename)
                            except Permission.DoesNotExist:
                                self.stdout.write(
                                    self.style.WARNING(f'⚠️ Кастомное право не найдено: {perm_codename}')
                                )

                except LookupError:
                    self.stdout.write(
                        self.style.ERROR('❌ Модель Article не найдена')
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Группа "{group_name}": добавлено {len(permissions_added)} прав\n'
                    f'   Права: {", ".join(permissions_added[:10])}'
                    f'{"..." if len(permissions_added) > 10 else ""}'
                )
            )

        self.stdout.write(
            self.style.SUCCESS('🎉 Настройка прав групп завершена!')
        )

        # Выводим информацию о созданных группах
        self.stdout.write('\n📊 Итоговая статистика:')
        for group in Group.objects.all():
            count = group.permissions.count()
            users = group.user_set.count()
            self.stdout.write(
                f'   👥 {group.name}: {count} прав, {users} пользователей'
            )