# wiki/utils/test_warnings.py
from django.contrib.auth.models import User
from wiki.models import UserWarning, UserBan
from django.utils import timezone


def test_warning_system(username):
    """Тестирует систему предупреждений и авто-бана"""
    try:
        user = User.objects.get(username=username)

        print(f"\n=== Тест системы предупреждений для {username} ===")

        # Очищаем старые данные для теста
        UserWarning.objects.filter(user=user).delete()
        UserBan.objects.filter(user=user).delete()

        # Создаем 3 предупреждения
        for i in range(1, 4):
            warning = UserWarning.objects.create(
                user=user,
                issued_by=user,  # в реальности это будет модератор
                severity='medium',
                reason=f'Тестовое предупреждение #{i}',
                is_active=True
            )
            print(f"Создано предупреждение #{i}")

        # Проверяем счет
        warnings_count = UserWarning.objects.filter(user=user, is_active=True).count()
        print(f"Активных предупреждений: {warnings_count}")

        # Проверяем есть ли бан
        has_ban = UserBan.objects.filter(user=user, is_active=True).exists()
        print(f"Есть активный бан: {has_ban}")

        # Создаем 4-е предупреждение (должен создаться бан)
        warning = UserWarning.objects.create(
            user=user,
            issued_by=user,
            severity='high',
            reason='Тестовое предупреждение #4 (должен вызвать бан)',
            is_active=True
        )
        print("Создано предупреждение #4")

        # Проверяем создался ли бан
        bans = UserBan.objects.filter(user=user, is_active=True)
        if bans.exists():
            ban = bans.first()
            print(f"✅ АВТОМАТИЧЕСКИЙ БАН СОЗДАН!")
            print(f"   Причина: {ban.get_reason_display()}")
            print(f"   Длительность: {ban.get_duration_display()}")
            print(f"   Истекает: {ban.expires_at}")
        else:
            print("❌ Бан не создался автоматически")

        return True

    except User.DoesNotExist:
        print(f"❌ Пользователь {username} не найден")
        return False