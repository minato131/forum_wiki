# wiki/middleware/censor_simple.py
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.contrib import messages


class CensorSimpleMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response
        self.bad_words = ['хуй', 'пизд', 'ебан', 'бля', 'сука', 'пидор']

    def __call__(self, request):
        # Проверяем POST запросы
        if request.method == 'POST' and request.user.is_authenticated:
            for field_name, field_value in request.POST.items():
                if isinstance(field_value, str):
                    text_lower = field_value.lower()
                    for bad_word in self.bad_words:
                        if bad_word in text_lower:
                            messages.error(request, '🚫 НЕЦЕНЗУРНАЯ ЛЕКСИКА! Сообщение отклонено.')
                            # Записываем нарушение
                            try:
                                from wiki.models import CensorshipWarning
                                CensorshipWarning.objects.create(
                                    user=request.user,
                                    text=field_value[:500],
                                    source_url=request.path
                                )
                            except:
                                pass
                            return redirect(request.META.get('HTTP_REFERER', '/'))

        response = self.get_response(request)
        return response