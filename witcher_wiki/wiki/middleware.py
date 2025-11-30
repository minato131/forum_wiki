import json
from django.utils import timezone
from .models import ActionLog
from .logging_utils import ActionLogger


class ActionLoggingMiddleware:
    """Middleware для автоматического логирования действий пользователей"""

    def __init__(self, get_response):
        self.get_response = get_response
        self.ignored_paths = [
            '/static/',
            '/media/',
            '/favicon.ico',
            '/admin/jsi18n/',
            '/__debug__/',
        ]

    def __call__(self, request):
        # Обрабатываем запрос
        response = self.get_response(request)

        # Логируем действие после обработки запроса
        self._log_action(request, response)

        return response

    def _should_log_request(self, request):
        """Проверяет, нужно ли логировать этот запрос"""
        # Не логируем неаутентифицированных пользователей
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            print(f"DEBUG: Not logging - user not authenticated: {request.path}")
            return False

        # Не логируем статические файлы и служебные пути
        path = request.path
        if any(path.startswith(ignored) for ignored in self.ignored_paths):
            print(f"DEBUG: Not logging - ignored path: {path}")
            return False

        # Не логируем AJAX-запросы (опционально)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            print(f"DEBUG: Not logging - AJAX request: {path}")
            return False

        print(f"DEBUG: Should log: {request.method} {path} - User: {request.user.username}")
        return True

    def _log_action(self, request, response):
        """Логирует действие пользователя"""
        if not self._should_log_request(request):
            return

        action_type = self._determine_action_type(request, response)
        if action_type:
            description = self._generate_description(request, action_type)

            print(f"DEBUG: Logging action: {action_type} - {description}")

            try:
                ActionLogger.log_action(
                    request=request,
                    action_type=action_type,
                    description=description,
                    extra_data={
                        'path': request.path,
                        'method': request.method,
                        'status_code': response.status_code,
                        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
                    }
                )
                print(f"DEBUG: Successfully logged action: {action_type}")
            except Exception as e:
                print(f"ERROR: Failed to log action: {e}")

    def _determine_action_type(self, request, response):
        """Определяет тип действия на основе запроса и ответа"""
        path = request.path
        method = request.method

        print(f"DEBUG: Determining action for {method} {path}, status: {response.status_code}")

        # Только успешные запросы
        if response.status_code not in [200, 201, 302, 304]:
            print(f"DEBUG: Skipping - status code {response.status_code}")
            return None

        # Логирование по путям и методам
        action_map = {
            ('/login/', 'POST'): 'login',
            ('/logout/', 'POST'): 'logout',
            ('/register/', 'POST'): 'user_register',
            ('/article/create/', 'POST'): 'article_create',
            ('/search/', 'GET'): 'search',
            ('/accounts/profile/', 'POST'): 'profile_update',
        }

        # Проверяем точные совпадения
        for (action_path, action_method), action_name in action_map.items():
            if path == action_path and method == action_method:
                print(f"DEBUG: Found exact match: {action_name}")
                return action_name

        # Проверяем частичные совпадения
        if '/article/' in path and '/edit/' in path and method == 'POST':
            return 'article_edit'
        elif '/article/' in path and '/delete/' in path and method == 'POST':
            return 'article_delete'
        elif '/article/' in path and '/moderate/' in path and method == 'POST':
            return 'article_moderate'
        elif '/article/' in path and '/like/' in path and method == 'POST':
            return 'article_like'
        elif '/category/' in path and '/create/' in path and method == 'POST':
            return 'category_create'
        elif '/category/' in path and '/edit/' in path and method == 'POST':
            return 'category_edit'
        elif '/category/' in path and '/delete/' in path and method == 'POST':
            return 'category_delete'
        elif '/message/' in path and method == 'POST':
            return 'message_send'
        elif method == 'GET' and response.status_code == 200:
            if '/article/' in path:
                return 'article_view'
            elif '/category/' in path:
                return 'category_view'
            elif '/user/' in path:
                return 'profile_view'
            elif path == '/':
                return 'home_view'

        print(f"DEBUG: No action type determined for {method} {path}")
        return None

    def _generate_description(self, request, action_type):
        """Генерирует описание действия"""
        username = request.user.username

        descriptions = {
            'login': f'Пользователь {username} вошел в систему',
            'logout': f'Пользователь {username} вышел из системы',
            'user_register': f'Зарегистрирован новый пользователь {username}',
            'article_create': f'Пользователь {username} создал статью',
            'article_edit': f'Пользователь {username} отредактировал статью',
            'article_delete': f'Пользователь {username} удалил статью',
            'article_view': f'Пользователь {username} просмотрел статью',
            'article_moderate': f'Модератор {username} выполнил модерацию статьи',
            'article_like': f'Пользователь {username} поставил/убрал лайк статье',
            'category_create': f'Пользователь {username} создал категорию',
            'category_edit': f'Пользователь {username} отредактировал категорию',
            'category_delete': f'Пользователь {username} удалил категорию',
            'category_view': f'Пользователь {username} просмотрел категорию',
            'message_send': f'Пользователь {username} отправил сообщение',
            'search': f'Пользователь {username} выполнил поиск',
            'profile_update': f'Пользователь {username} обновил профиль',
            'profile_view': f'Пользователь {username} просмотрел профиль',
            'home_view': f'Пользователь {username} посетил главную страницу',
        }

        return descriptions.get(action_type, f'Пользователь {username} выполнил действие {action_type}')