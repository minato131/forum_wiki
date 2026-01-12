# wiki/management/commands/check_user_permissions.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db.models import Q


class Command(BaseCommand):
    help = 'Проверка прав конкретного пользователя'

    def add_arguments(self, parser):
        parser.add_argument(
            'username',
            type=str,
            help='Имя пользователя для проверки прав'
        )

    def handle(self, *args, **options):
        username = options['username']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Пользователь {username} не найден'))
            return

        self.stdout.write(f'👤 Пользователь: {user.username} ({user.email})')
        self.stdout.write(f'   📝 ФИО: {user.first_name} {user.last_name}')
        self.stdout.write(f'   🏢 Статус: {"👑 Суперпользователь" if user.is_superuser else "👤 Обычный пользователь"}')
        self.stdout.write(f'   🔧 Персонал: {"✅ Да" if user.is_staff else "❌ Нет"}')

        # Группы пользователя
        groups = user.groups.all()
        if groups:
            self.stdout.write(f'   👥 Группы: {", ".join([g.name for g in groups])}')
        else:
            self.stdout.write('   👥 Группы: Нет')

        # Все права пользователя
        all_perms = user.get_all_permissions()
        self.stdout.write(f'   🔑 Всего прав: {len(all_perms)}')

        if all_perms:
            # Группируем права по приложениям
            perms_by_app = {}
            for perm in sorted(all_perms):
                # Формат: "wiki.add_article"
                app, codename = perm.split('.')
                if app not in perms_by_app:
                    perms_by_app[app] = []
                perms_by_app[app].append(codename)

            for app, perms in perms_by_app.items():
                self.stdout.write(f'      📁 {app.upper()}:')
                # Группируем по моделям
                perms_by_model = {}
                for codename in perms:
                    if '_' in codename:
                        action, model = codename.split('_', 1)
                        if model not in perms_by_model:
                            perms_by_model[model] = []
                        perms_by_model[model].append(action)

                for model, actions in perms_by_model.items():
                    actions_str = ', '.join(sorted(set(actions)))
                    self.stdout.write(f'         • {model}: {actions_str}')

        # Прямые права пользователя (не через группы)
        direct_perms = user.user_permissions.all()
        if direct_perms:
            self.stdout.write(f'   🔧 Прямые права: {direct_perms.count()}')
            for perm in direct_perms:
                self.stdout.write(f'      • {perm.codename}')

        # Проверка наличия конкретных важных прав
        important_perms = [
            ('can_moderate', 'Может модерировать'),
            ('can_edit_any_articles', 'Может редактировать любые статьи'),
            ('can_access_admin', 'Доступ к админке'),
            ('can_manage_users', 'Может управлять пользователями'),
        ]

        self.stdout.write('\n   📊 Ключевые права:')
        for perm, desc in important_perms:
            has_perm = user.has_perm(f'wiki.{perm}')
            status = '✅' if has_perm else '❌'
            self.stdout.write(f'      {status} {desc}')

        self.stdout.write(self.style.SUCCESS(f'\n✅ Проверка прав пользователя {username} завершена'))