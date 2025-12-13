# wiki/utils/warning_utils.py
from django.utils import timezone
from wiki.models import UserWarning, UserBan
from datetime import timedelta


def check_user_warnings(user):
    """Проверяет активные предупреждения пользователя"""
    # Считаем активные предупреждения
    active_warnings = UserWarning.objects.filter(
        user=user,
        is_active=True,
        # Можно добавить проверку по времени если нужно
        # created_at__gte=timezone.now() - timedelta(days=30)
    ).count()

    return active_warnings


def apply_auto_ban_if_needed(user, warning_creator):
    """Применяет автоматический бан если нужно (4+ предупреждений = бан на 1 день)"""
    active_warnings = check_user_warnings(user)

    if active_warnings >= 4:
        # Проверяем нет ли уже активного бана
        existing_ban = UserBan.objects.filter(
            user=user,
            is_active=True
        ).first()

        # Проверяем не истек ли бан
        should_create_ban = True
        if existing_ban:
            if existing_ban.duration == 'permanent':
                should_create_ban = False  # Уже есть перманентный бан
            elif existing_ban.expires_at and existing_ban.expires_at > timezone.now():
                should_create_ban = False  # Уже есть активный временный бан

        if should_create_ban:
            # Создаем бан на 1 день
            ban = UserBan.objects.create(
                user=user,
                banned_by=warning_creator,
                reason='multiple_violations',
                duration='1d',
                notes=f'Автоматический бан за {active_warnings} активных предупреждений',
                is_active=True
            )

            # Можно добавить логирование
            print(f"✅ Автоматический бан создан для {user.username} за {active_warnings} предупреждений")
            return True

    return False