# wiki/management/commands/check_auto_bans.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db.models import Q, Count
from wiki.models import UserWarning, UserBan
from django.utils import timezone


class Command(BaseCommand):
    help = 'Проверяет и применяет автоматические баны за предупреждения'

    def handle(self, *args, **options):
        self.stdout.write("🔍 Проверка авто-банов...")

        # Находим всех пользователей с 4+ предупреждениями
        users_to_check = User.objects.annotate(
            warning_count=Count('user_warnings', filter=Q(user_warnings__is_active=True))
        ).filter(warning_count__gte=4)

        for user in users_to_check:
            warnings_count = user.warning_count

            # Проверяем нет ли уже активного бана
            has_active_ban = UserBan.objects.filter(
                user=user,
                is_active=True
            ).exists()

            if not has_active_ban:
                # Создаем бан
                last_warning = UserWarning.objects.filter(
                    user=user
                ).order_by('-created_at').first()

                issuer = last_warning.issued_by if last_warning else user

                ban = UserBan.objects.create(
                    user=user,
                    banned_by=issuer,
                    reason='multiple_violations',
                    duration='1d',
                    notes=f'Автоматический бан за {warnings_count} активных предупреждений',
                    is_active=True
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Создан авто-бан для {user.username} "
                        f"за {warnings_count} предупреждений"
                    )
                )

        self.stdout.write(self.style.SUCCESS("Проверка завершена"))