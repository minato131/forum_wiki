from django.shortcuts import redirect
from django.contrib import messages
import re


class CensorshipMiddleware:
    """Middleware для цензуры контента"""

    def __init__(self, get_response):
        self.get_response = get_response
        # Список запрещенных слов
        self.banned_words = [
            'хуй', 'пизда', 'еблан', 'мудак', 'говно',
            'fuck', 'shit', 'asshole', 'bitch'
        ]

    def __call__(self, request):
        # Проверяем только аутентифицированных пользователей
        if not request.user.is_authenticated:
            response = self.get_response(request)
            return response

        # Проверяем POST-запросы на создание/редактирование контента
        if request.method == 'POST':
            # Определяем какой контент создается
            content_paths = [
                '/article/create/',
                '/article/',  # редактирование статей
                '/comment/',  # комментарии
            ]

            should_check = False
            for path in content_paths:
                if request.path.startswith(path):
                    should_check = True
                    break

            if should_check:
                found_banned_words = []

                # Проверяем все текстовые поля
                for key, value in request.POST.items():
                    if isinstance(value, str) and value.strip():
                        for word in self.banned_words:
                            pattern = r'\b' + re.escape(word) + r'\b'
                            if re.search(pattern, value, re.IGNORECASE):
                                if word not in found_banned_words:
                                    found_banned_words.append(word)

                if found_banned_words:
                    # БЛОКИРУЕМ создание контента
                    try:
                        from wiki.models import UserWarning
                        from wiki.utils.warning_utils import apply_auto_ban_if_needed

                        # Создаем предупреждение
                        warning = UserWarning.objects.create(
                            user=request.user,
                            issued_by=request.user,  # или системный пользователь
                            severity='medium',
                            reason=f'Использование запрещенных слов: {", ".join(found_banned_words)}',
                            related_content=f'Попытка создания контента по пути: {request.path}',
                            is_active=True
                        )

                        # Проверяем нужно ли автоматически забанить
                        was_banned = apply_auto_ban_if_needed(request.user, request.user)

                        # Считаем общее количество предупреждений
                        warnings_count = UserWarning.objects.filter(
                            user=request.user,
                            is_active=True
                        ).count()

                        if was_banned:
                            messages.error(request,
                                           f'❌ Обнаружена нецензурная лексика! Вам выдано предупреждение. '
                                           f'У вас {warnings_count} активных предупреждений - АВТОМАТИЧЕСКИЙ БАН на 1 день.'
                                           )
                        else:
                            messages.error(request,
                                           f'❌ Обнаружена нецензурная лексика! Вам выдано предупреждение. '
                                           f'У вас {warnings_count}/4 активных предупреждений. '
                                           f'После 4 предупреждений - автоматический бан на 1 день.'
                                           )

                        # Редиректим обратно и НЕ СОЗДАЕМ контент
                        return redirect(request.META.get('HTTP_REFERER', '/'))

                    except Exception as e:
                        # Если ошибка при создании предупреждения, все равно блокируем
                        messages.error(request,
                                       f'❌ Ваше сообщение содержит запрещенные слова: {", ".join(found_banned_words)}. '
                                       f'Создание контента заблокировано.'
                                       )
                        return redirect(request.META.get('HTTP_REFERER', '/'))

        response = self.get_response(request)
        return response