# wiki/middleware/ban_check_middleware.py
from django.shortcuts import redirect
from django.utils import timezone
from django.urls import reverse
from wiki.models import UserWarning
from wiki.models import UserBan
from django.http import HttpResponseRedirect


class BanCheckMiddleware:
    """Middleware для проверки активных банов пользователя"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Исключаем некоторые URL из проверки
        exempt_paths = [
            '/banned/',
            '/accounts/login/',
            '/accounts/logout/',
            '/accounts/register/',
            '/admin/',
        ]

        # Если путь в исключениях - пропускаем проверку
        if any(request.path.startswith(path) for path in exempt_paths):
            response = self.get_response(request)
            return response

        # Проверяем только аутентифицированных пользователей
        if request.user.is_authenticated:
            try:
                from wiki.models import UserBan

                # Ищем активные баны
                active_bans = UserBan.objects.filter(
                    user=request.user,
                    is_active=True
                )

                current_time = timezone.now()
                has_active_ban = False

                for ban in active_bans:
                    if ban.duration == 'permanent':
                        # Постоянный бан - всегда активен
                        has_active_ban = True
                        break
                    elif ban.expires_at and ban.expires_at > current_time:
                        # Временный бан еще не истек
                        has_active_ban = True
                        break
                    else:
                        # Бан истек - деактивируем его
                        ban.is_active = False
                        ban.save()

                if has_active_ban:
                    # Если пользователь забанен и не на странице бана
                    if not request.path.startswith('/banned/'):
                        # Редирект на страницу бана
                        return HttpResponseRedirect('/banned/')

            except Exception as e:
                print(f"Error in BanCheckMiddleware: {e}")
                # В случае ошибки продолжаем выполнение

        # Всегда возвращаем response, даже если он None от следующего middleware
        response = self.get_response(request)

        # Если response None, создаем пустой response
        if response is None:
            from django.http import HttpResponse
            response = HttpResponse("")

        return response