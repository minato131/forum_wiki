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
        # Проверяем POST-запросы на наличие запрещенных слов
        if request.method == 'POST':
            for key, value in request.POST.items():
                if isinstance(value, str):
                    for word in self.banned_words:
                        pattern = r'\b' + re.escape(word) + r'\b'
                        if re.search(pattern, value, re.IGNORECASE):
                            messages.error(request, 'Ваше сообщение содержит запрещенные слова!')
                            # Редиректим обратно
                            return redirect(request.META.get('HTTP_REFERER', '/'))

        response = self.get_response(request)
        return response