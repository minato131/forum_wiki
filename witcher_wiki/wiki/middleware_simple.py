
from .logging_utils import ActionLogger
from .censorship import CensorshipService
from .censorship_warnings import CensorshipWarningSystem
from .moderation_service import ModerationService

class ActionLoggingMiddleware:
    """Улучшенное middleware для логирования ВСЕХ действий пользователей, включая админку"""

    def __init__(self, get_response):
        self.get_response = get_response
        self.ignored_paths = [
            '/static/',
            '/media/',
            '/favicon.ico',
            '/admin/jsi18n/',
            '/__debug__/',
            '/admin/static/',
        ]

        # Действия в админке, которые нужно логировать
        self.admin_actions = {
            'add': 'создание',
            'change': 'редактирование',
            'delete': 'удаление',
            'history': 'просмотр истории',
            'changelist': 'просмотр списка',
        }

    def _check_censorship(self, request):
        """Проверяет POST запросы на наличие запрещенных слов"""
        if request.method != 'POST':
            return

        # Проверяем только определенные пути
        censorship_paths = [
            '/wiki/article/create/',
            '/wiki/article/edit/',
            '/wiki/comment/add/',
            '/wiki/comment/reply/',
            '/accounts/profile/update/',
            '/admin/wiki/article/add/',
            '/admin/wiki/article/',
        ]

        # Проверяем, нужно ли проверять этот путь
        should_check = False
        for path in censorship_paths:
            if request.path.startswith(path):
                should_check = True
                break

        if not should_check:
            return

        # Проверяем POST данные
        banned_words_found = []

        for field_name, field_value in request.POST.items():
            if isinstance(field_value, str) and len(field_value) > 3:
                has_banned, found_words, _ = CensorshipService.contains_banned_words(field_value)

                if has_banned:
                    for word in found_words:
                        banned_words_found.append({
                            'field': field_name,
                            'word': word,
                            'value_preview': field_value[:50] + ('...' if len(field_value) > 50 else '')
                        })

        # Если нашли запрещенные слова, добавляем их в request
        if banned_words_found:
            request.censorship_violation = True
            request.banned_words_found = banned_words_found[:5]  # Ограничиваем количество

            # Логируем попытку нарушения
            if request.user.is_authenticated:
                username = request.user.username
                words_list = ', '.join(set([item['word'] for item in banned_words_found[:3]]))

                print(f"⚠️ ЦЕНЗУРА: Пользователь {username} попытался отправить запрещенные слова: {words_list}")
                print(f"   Путь: {request.path}")
                print(f"   Метод: {request.method}")

    def __call__(self, request):

        self._check_censorship(request)
        # Обрабатываем запрос
        response = self.get_response(request)

        # Логируем действие после обработки запроса
        self._log_action(request, response)

        return response

    def _should_log_request(self, request):
        """Проверяет, нужно ли логировать этот запрос"""
        # Не логируем статические файлы и служебные пути
        path = request.path
        if any(path.startswith(ignored) for ignored in self.ignored_paths):
            return False

        # Не логируем AJAX-запросы для уменьшения шума
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return False

        # Для админки логируем всё, кроме анонимов
        if path.startswith('/admin/'):
            return request.user.is_authenticated

        # Для остальных путей логируем только аутентифицированных
        return hasattr(request, 'user') and request.user.is_authenticated

    def _log_action(self, request, response):
        """Логирует действие пользователя"""
        if not self._should_log_request(request):
            return

        action_type, model_name, action_details = self._determine_admin_action(request, response)

        if not action_type:
            action_type = self._determine_action_type(request, response)

        if action_type:
            description = self._generate_description(
                request,
                action_type,
                model_name,
                action_details
            )

            print(f"DEBUG: Logging action: {action_type} - {description}")

            try:
                # Собираем дополнительные данные
                extra_data = {
                    'path': request.path,
                    'method': request.method,
                    'status_code': response.status_code,
                    'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
                    'referer': request.META.get('HTTP_REFERER', ''),
                }

                # Для админ действий добавляем детали
                if model_name:
                    extra_data['model'] = model_name
                if action_details:
                    extra_data.update(action_details)

                # Для POST запросов в админке логируем данные (кроме чувствительных)
                if request.method == 'POST' and request.path.startswith('/admin/'):
                    post_data = {}
                    for key, value in request.POST.items():
                        if any(sensitive in key.lower() for sensitive in ['password', 'secret', 'key', 'token']):
                            post_data[key] = '***HIDDEN***'
                        else:
                            post_data[key] = str(value)[:100]  # Ограничиваем длину
                    extra_data['post_data'] = post_data

                ActionLogger.log_action(
                    request=request,
                    action_type=action_type,
                    description=description,
                    extra_data=extra_data
                )

                print(f"DEBUG: Successfully logged action: {action_type}")
            except Exception as e:
                print(f"ERROR: Failed to log action: {e}")

    def _determine_admin_action(self, request, response):
        """Определяет действия в админ-панели"""
        path = request.path

        if not path.startswith('/admin/'):
            return None, None, None

        # Разбираем URL админки
        # Пример: /admin/wiki/article/1/change/
        parts = path.strip('/').split('/')

        if len(parts) < 4:
            return 'admin_access', None, {'section': parts[2] if len(parts) > 2 else 'index'}

        app_label = parts[2]  # wiki
        model_name = parts[3]  # article, category, etc.

        # Определяем действие
        if len(parts) >= 5:
            action = parts[4]
            if action in self.admin_actions:
                # Получаем ID объекта если есть
                object_id = parts[4] if len(parts) > 5 and parts[4].isdigit() else None
                if object_id and len(parts) > 5:
                    action = parts[5]

                details = {
                    'app': app_label,
                    'model': model_name,
                    'object_id': object_id,
                    'action': action,
                }

                return f'admin_{action}', model_name, details

        # Для просмотра списка объектов
        elif len(parts) == 4:
            details = {
                'app': app_label,
                'model': model_name,
                'action': 'changelist',
            }
            return 'admin_changelist', model_name, details

        return 'admin_access', None, None

    def _determine_action_type(self, request, response):
        """Определяет тип действия для обычных запросов"""
        path = request.path
        method = request.method

        # Только успешные запросы
        if response.status_code not in [200, 201, 302, 304]:
            return None

        # Специальные пути для бэкапов
        if '/backup/' in path:
            if '/create/' in path and method == 'POST':
                return 'backup_create'
            elif '/download/' in path:
                return 'backup_download'
            elif '/restore/' in path and method == 'POST':
                return 'backup_restore'
            elif '/delete/' in path and method == 'POST':
                return 'backup_delete'
            elif path.endswith('/backup/'):
                return 'backup_list'

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

        return None

    def _generate_description(self, request, action_type, model_name=None, details=None):
        """Генерирует описание действия"""
        username = request.user.username

        # Описания для админ-действий
        if action_type.startswith('admin_'):
            action_display = self.admin_actions.get(
                action_type.replace('admin_', ''),
                action_type.replace('admin_', '')
            )

            if model_name:
                model_display = self._get_model_display_name(model_name)

                if details and details.get('object_id'):
                    return f'Администратор {username} выполнил {action_display} {model_display} (ID: {details["object_id"]})'
                else:
                    return f'Администратор {username} выполнил {action_display} {model_display}'
            else:
                return f'Администратор {username} получил доступ к админ-панели'

        # Описания для бэкапов
        elif 'backup' in action_type:
            backup_actions = {
                'backup_create': 'создал резервную копию',
                'backup_download': 'скачал резервную копию',
                'backup_restore': 'восстановил из резервной копии',
                'backup_delete': 'удалил резервную копию',
                'backup_list': 'просмотрел список резервных копий',
            }
            action_desc = backup_actions.get(action_type, 'выполнил операцию с бэкапом')
            return f'Администратор {username} {action_desc}'

        # Обычные описания
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

    def _get_model_display_name(self, model_name):
        """Получает читаемое название модели"""
        display_names = {
            'article': 'статью',
            'category': 'категорию',
            'comment': 'комментарий',
            'userprofile': 'профиль пользователя',
            'actionlog': 'лог действий',
            'backup': 'резервную копию',
            'backuplog': 'лог бэкапа',
            'articlerevision': 'версию статьи',
            'moderationcomment': 'комментарий модерации',
            'articlemedia': 'медиафайл статьи',
            'articlelike': 'лайк статьи',
            'message': 'сообщение',
            'searchquery': 'поисковый запрос',
            'emailverification': 'верификацию email',
            'telegramuser': 'пользователя Telegram',
            'authcode': 'код авторизации',
            'helsection': 'раздел помощи',
            'faq': 'FAQ',
            'articlestat': 'статистику статьи',
            'categorystat': 'статистику категории',
            'sitestat': 'статистику сайта',
            'usertutorial': 'туториал пользователя',
        }

        return display_names.get(model_name, model_name)


def _check_censorship(self, request):
    """Проверяет POST запросы на наличие запрещенных слов"""
    if request.method != 'POST':
        return

    # Проверяем только определенные пути
    censorship_paths = [
        '/wiki/article/create/',
        '/wiki/article/edit/',
        '/wiki/comment/add/',
        '/wiki/comment/reply/',
        '/accounts/profile/update/',
        '/admin/wiki/article/add/',
        '/admin/wiki/article/',
    ]

    # Проверяем, нужно ли проверять этот путь
    should_check = False
    for path in censorship_paths:
        if request.path.startswith(path):
            should_check = True
            break

    if not should_check:
        return

    # Проверяем POST данные
    banned_words_found = []
    all_banned_words = []

    for field_name, field_value in request.POST.items():
        if isinstance(field_value, str) and len(field_value) > 3:
            has_banned, found_words, _ = CensorshipService.contains_banned_words(field_value)

            if has_banned:
                for word in found_words:
                    banned_words_found.append({
                        'field': field_name,
                        'word': word,
                        'value_preview': field_value[:50] + ('...' if len(field_value) > 50 else '')
                    })
                    all_banned_words.append(word)

    # Если нашли запрещенные слова
    if banned_words_found:
        # Убираем дубликаты
        unique_words = list(set(all_banned_words))

        # Добавляем в request
        request.censorship_violation = True
        request.banned_words_found = banned_words_found[:5]
        request.banned_words_unique = unique_words

        # Получаем количество предупреждений пользователя
        if request.user.is_authenticated:
            warning_count = CensorshipWarningSystem.get_user_warnings(request.user)

            # Логируем попытку нарушения
            words_list = ', '.join(unique_words[:3])
            if len(unique_words) > 3:
                words_list += f' и еще {len(unique_words) - 3}...'

            print(f"⚠️ ЦЕНЗУРА: Пользователь {request.user.username} (нарушений: {warning_count + 1})")
            print(f"   Слова: {words_list}")
            print(f"   Путь: {request.path}")

            # Добавляем сообщение о предупреждении
            warning_message = CensorshipWarningSystem.handle_censorship_violation(request, unique_words)
            request.censorship_warning_message = warning_message


class BanCheckMiddleware:
    """Middleware для проверки забаненных пользователей"""

    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_paths = [
            '/admin/',
            '/accounts/login/',
            '/accounts/logout/',
            '/accounts/register/',
            '/accounts/password/reset/',
            '/static/',
            '/media/',
            '/api/',
        ]

    def __call__(self, request):
        # Проверяем только аутентифицированных пользователей
        if request.user.is_authenticated:
            user_status = ModerationService.get_user_status(request.user)

            if user_status['is_banned']:
                # Разрешаем доступ к некоторым путям
                if any(request.path.startswith(path) for path in self.allowed_paths):
                    return self.get_response(request)

                # Для забаненных показываем страницу бана
                from django.shortcuts import render
                return render(request, 'wiki/banned.html', {
                    'user_status': user_status,
                    'ban': user_status['ban_details'],
                })

        return self.get_response(request)