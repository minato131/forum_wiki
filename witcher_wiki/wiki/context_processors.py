# wiki/context_processors.py
def user_permissions(request):
    """Добавляет переменные прав пользователя в контекст"""

    def can_moderate(user):
        return (user.is_authenticated and
                (user.is_staff or
                 user.groups.filter(name__in=['Модератор', 'Администратор']).exists()))

    def can_edit_content(user):
        return (user.is_authenticated and
                (user.is_staff or
                 user.groups.filter(name__in=['Редактор', 'Модератор', 'Администратор']).exists()))

    def is_admin(user):
        return user.is_authenticated and (user.is_staff or user.groups.filter(name='Администратор').exists())

    return {
        'user_can_moderate': can_moderate(request.user) if request.user.is_authenticated else False,
        'user_can_edit': can_edit_content(request.user) if request.user.is_authenticated else False,
        'user_is_admin': is_admin(request.user) if request.user.is_authenticated else False,
    }