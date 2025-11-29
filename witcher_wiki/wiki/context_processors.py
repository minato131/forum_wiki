from django.conf import settings
# wiki/context_processors.py
from django.contrib.auth.models import Group


def user_permissions(request):
    """Добавляет информацию о правах пользователя в контекст"""
    user_can_moderate = False
    user_can_edit = False
    user_can_manage_categories = False

    if request.user.is_authenticated:
        user_groups = request.user.groups.all()
        group_names = [group.name for group in user_groups]

        user_can_moderate = (
                request.user.is_staff or
                'Модератор' in group_names or
                'Администратор' in group_names
        )

        user_can_edit = (
                request.user.is_staff or
                'Редактор' in group_names or
                'Модератор' in group_names or
                'Администратор' in group_names
        )

        user_can_manage_categories = (
                request.user.is_staff or
                'Модератор' in group_names or
                'Администратор' in group_names
        )

    return {
        'user_can_moderate': user_can_moderate,
        'user_can_edit': user_can_edit,
        'user_can_manage_categories': user_can_manage_categories,
    }
def telegram_settings(request):
    """Добавляет настройки Telegram в контекст шаблонов"""
    return {
        'telegram_bot_username': getattr(settings, 'TELEGRAM_BOT_USERNAME', ''),
        'TELEGRAM_BOT_USERNAME': getattr(settings, 'TELEGRAM_BOT_USERNAME', ''),
        'TELEGRAM_WEB_APP_URL': getattr(settings, 'TELEGRAM_WEB_APP_URL', ''),
    }