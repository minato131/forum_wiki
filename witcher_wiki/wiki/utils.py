from django.contrib.auth.models import Group

def user_can_moderate(user):
    """Проверяет, может ли пользователь модерировать"""
    return (user.is_staff or
            user.groups.filter(name__in=['Модератор', 'Администратор']).exists() or
            user.has_perm('wiki.can_moderate'))

def user_can_edit_content(user):
    """Проверяет, может ли пользователь редактировать контент"""
    return (user.is_staff or
            user.groups.filter(name__in=['Редактор', 'Модератор', 'Администратор']).exists() or
            user.has_perm('wiki.can_edit_content'))

def user_can_manage_categories(user):
    """Проверяет, может ли пользователь управлять категориями"""
    return (user.is_staff or
            user.groups.filter(name__in=['Модератор', 'Администратор']).exists() or
            user.has_perm('wiki.can_manage_categories'))

def user_is_admin(user):
    """Проверяет, является ли пользователь администратором"""
    return user.is_staff or user.groups.filter(name='Администратор').exists()