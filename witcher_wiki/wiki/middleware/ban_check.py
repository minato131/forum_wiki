# wiki/middleware/ban_simple.py
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone


class BanSimpleMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                from wiki.models import UserBan

                # Ищем активные баны
                active_bans = UserBan.objects.filter(
                    user=request.user,
                    is_active=True
                )

                for ban in active_bans:
                    if not ban.is_expired():
                        # Разрешаем только главную и выход
                        if request.path not in ['/', '/accounts/logout/', '/accounts/login/']:
                            messages.error(
                                request,
                                f'🚫 ВАШ АККАУНТ ЗАБАНЕН до {ban.expires_at.strftime("%d.%m.%Y %H:%M")}! '
                                f'Причина: {ban.get_reason_display()}'
                            )
                            return redirect('/')
                        break

            except Exception as e:
                print(f"[BAN ERROR] {e}")

        response = self.get_response(request)
        return response