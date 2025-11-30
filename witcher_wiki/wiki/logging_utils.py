import json
import uuid
from user_agents import parse
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from .models import ActionLog


class ActionLogger:
    """Класс для логирования действий пользователей"""

    @staticmethod
    def get_client_info(request):
        """Извлекает информацию о клиенте из запроса"""
        user_agent = parse(request.META.get('HTTP_USER_AGENT', ''))

        return {
            'ip_address': ActionLogger.get_client_ip(request),
            'browser': f"{user_agent.browser.family} {user_agent.browser.version_string}",
            'operating_system': f"{user_agent.os.family} {user_agent.os.version_string}",
            'device': f"{user_agent.device.family}",
            'user_agent': str(user_agent),
        }

    @staticmethod
    def get_client_ip(request):
        """Получает реальный IP-адрес клиента"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    @classmethod
    def log_action(cls, request, action_type, description, target_object=None, extra_data=None):
        """Основной метод логирования действий"""

        # Подготавливаем данные
        client_info = cls.get_client_info(request)
        action_data = extra_data or {}

        if target_object:
            content_type = ContentType.objects.get_for_model(target_object)
            object_id = target_object.pk
        else:
            content_type = None
            object_id = None

        # Создаем запись лога
        log_entry = ActionLog(
            user=request.user if request.user.is_authenticated else None,
            action_type=action_type,
            description=description,
            ip_address=client_info['ip_address'],
            user_agent=client_info['user_agent'],
            browser=client_info['browser'],
            operating_system=client_info['operating_system'],
            action_data=action_data,
            content_type=content_type,
            object_id=object_id,
        )

        log_entry.save()
        return log_entry


# Декоратор для автоматического логирования функций
def log_user_action(action_type, description_template=None, get_target_object=None):
    """Декоратор для автоматического логирования действий пользователей"""

    def decorator(view_func):
        def wrapped(request, *args, **kwargs):
            # Выполняем view функцию
            response = view_func(request, *args, **kwargs)

            # Логируем действие если пользователь аутентифицирован
            if request.user.is_authenticated:
                # Формируем описание
                if description_template:
                    description = description_template.format(
                        user=request.user.username,
                        **kwargs
                    )
                else:
                    description = f"Пользователь {request.user.username} выполнил действие"

                # Получаем целевой объект если указано
                target_object = None
                if get_target_object:
                    target_object = get_target_object(request, *args, **kwargs)

                # Логируем действие
                ActionLogger.log_action(
                    request=request,
                    action_type=action_type,
                    description=description,
                    target_object=target_object
                )

            return response

        return wrapped

    return decorator


# Упрощенные методы для частых действий
def log_article_creation(request, article):
    """Логирует создание статьи"""
    return ActionLogger.log_action(
        request=request,
        action_type='article_create',
        description=f'Пользователь {request.user.username} создал статью "{article.title}"',
        target_object=article,
        extra_data={
            'article_title': article.title,
            'article_slug': article.slug,
            'article_status': article.status,
        }
    )


def log_article_moderation(request, article, action, notes=''):
    """Логирует действия модерации"""
    action_descriptions = {
        'approve': 'одобрил',
        'reject': 'отклонил',
        'needs_correction': 'отправил на доработку',
        'send_to_editor': 'отправил редактору',
    }

    return ActionLogger.log_action(
        request=request,
        action_type='article_moderate',
        description=f'Модератор {request.user.username} {action_descriptions.get(action, action)} статью "{article.title}"',
        target_object=article,
        extra_data={
            'article_title': article.title,
            'moderation_action': action,
            'moderation_notes': notes,
        }
    )


def log_user_login(request):
    """Логирует вход пользователя"""
    return ActionLogger.log_action(
        request=request,
        action_type='login',
        description=f'Пользователь {request.user.username} вошел в систему',
        extra_data={'login_method': 'standard'}
    )


def log_user_logout(request):
    """Логирует выход пользователя"""
    return ActionLogger.log_action(
        request=request,
        action_type='logout',
        description=f'Пользователь {request.user.username} вышел из системы'
    )