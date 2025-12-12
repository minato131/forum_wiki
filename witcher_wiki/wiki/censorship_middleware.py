# wiki/censorship_middleware.py
from django.contrib import messages
from .censorship_warnings import CensorshipWarningSystem


class CensorshipResponseMiddleware:
    """
    Middleware для обработки результатов проверки цензуры.
    Работает ПОСЛЕ обычных middleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Если в request есть информация о нарушении цензуры
        if hasattr(request, 'censorship_violation') and request.censorship_violation:
            self._handle_censorship_violation(request, response)

        return response

    def _handle_censorship_violation(self, request, response):
        """Обрабатывает нарушение цензуры"""
        if not hasattr(request, 'banned_words_unique'):
            return

        banned_words = request.banned_words_unique

        if not banned_words:
            return

        # Получаем сообщение о предупреждении
        if hasattr(request, 'censorship_warning_message'):
            warning_message = request.censorship_warning_message
        else:
            warning_message = CensorshipWarningSystem.handle_censorship_violation(request, banned_words)

        # Разделяем сообщение на части
        message_lines = warning_message.split('\n')

        # Первая строка - основное сообщение
        if message_lines:
            messages.error(request, message_lines[0])

        # Вторая строка - детали нарушения
        if len(message_lines) > 1:
            messages.warning(request, message_lines[1])

        # Остальные строки - для админов
        if len(message_lines) > 2 and request.user.is_staff:
            for line in message_lines[2:]:
                if line.strip():
                    messages.info(request, line)