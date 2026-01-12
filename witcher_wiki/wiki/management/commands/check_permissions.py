# Создайте файл wiki/management/commands/check_permissions.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = 'Проверка прав для всех групп и пользователей'

    def handle(self, *args, **options):
        self.stdout.write('🔍 Проверка прав для групп...\n')

        # Проверяем группы
        for group in Group.objects.all():
            self.stdout.write(f'👥 Группа: {group.name}')
            self.stdout.write(f'   👤 Пользователей в группе: {group.user_set.count()}')

            # Права группы
            permissions = group.permissions.all()
            if permissions:
                self.stdout.write(f'   🔑 Прав: {permissions.count()}')
                # Группируем права по модели
                perms_by_model = {}
                for perm in permissions:
                    model_name = perm.content_type.model
                    if model_name not in perms_by_model:
                        perms_by_model[model_name] = []
                    perms_by_model[model_name].append(perm.codename)

                for model, perms in perms_by_model.items():
                    self.stdout.write(f'      📁 {model}: {", ".join(sorted(perms))}')
            else:
                self.stdout.write('   ⚠️  Нет прав')

            self.stdout.write('')

        # Проверяем суперпользователей
        superusers = User.objects.filter(is_superuser=True)
        if superusers.exists():
            self.stdout.write('👑 Суперпользователи:')
            for user in superusers:
                self.stdout.write(f'   👤 {user.username} ({user.email})')

        self.stdout.write('\n✅ Проверка завершена')