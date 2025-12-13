# wiki/middleware/ban_check_middleware.py
from django.shortcuts import redirect
from django.utils import timezone
from django.urls import reverse


class BanCheckMiddleware:
    """Middleware для проверки активных банов пользователя"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        print(f"🟡 DEBUG MIDDLEWARE: Проверка пути: {request.path}")
        print(f"🟡 DEBUG MIDDLEWARE: Пользователь аутентифицирован: {request.user.is_authenticated}")

        # Исключаем некоторые URL из проверки
        exempt_paths = [
            '/banned/',
            '/accounts/login/',
            '/accounts/logout/',
            '/accounts/register/',
            '/admin/',
            '/admin/login/',
            '/logout/',
        ]

        # Если путь в исключениях - пропускаем проверку
        if any(request.path.startswith(path) for path in exempt_paths):
            print(f"🟡 DEBUG MIDDLEWARE: Путь в исключениях, пропускаем проверку")
            response = self.get_response(request)
            return response

        # Проверяем только аутентифицированных пользователей
        if request.user.is_authenticated:
            print(f"🟡 DEBUG MIDDLEWARE: Проверяем пользователя: {request.user.username}")

            try:
                from wiki.models import UserBan

                # Ищем активные баны
                active_bans = UserBan.objects.filter(
                    user=request.user,
                    is_active=True
                )

                print(f"🟡 DEBUG MIDDLEWARE: Найдено активных банов: {active_bans.count()}")

                current_time = timezone.now()
                has_active_ban = False

                for ban in active_bans:
                    print(f"🟡 DEBUG MIDDLEWARE: Проверяем бан ID {ban.id}")
                    print(f"  Тип: {ban.duration}, Истекает: {ban.expires_at}")

                    if ban.duration == 'permanent':
                        # Постоянный бан - всегда активен
                        print(f"🟡 DEBUG MIDDLEWARE: Постоянный бан - активен")
                        has_active_ban = True
                        break
                    elif ban.expires_at and ban.expires_at > current_time:
                        # Временный бан еще не истек
                        print(
                            f"🟡 DEBUG MIDDLEWARE: Временный бан активен (истекает через {ban.expires_at - current_time})")
                        has_active_ban = True
                        break
                    else:
                        # Бан истек - деактивируем его
                        print(f"🟡 DEBUG MIDDLEWARE: Бан истек, деактивируем")
                        ban.is_active = False
                        ban.save()

                if has_active_ban:
                    print(f"🔴 DEBUG MIDDLEWARE: Пользователь {request.user.username} ЗАБАНЕН!")
                    print(f"🔴 DEBUG MIDDLEWARE: Текущий путь: {request.path}")

                    # Редирект на страницу бана
                    banned_url = reverse('wiki:banned')
                    print(f"🔴 DEBUG MIDDLEWARE: Редирект на {banned_url}")

                    # Если мы уже на странице бана - не редиректим
                    if not request.path.startswith('/banned/'):
                        return redirect('wiki:banned')
                    else:
                        print(f"🟡 DEBUG MIDDLEWARE: Уже на странице бана, не редиректим")

            except ImportError as e:
                print(f"🔴 DEBUG MIDDLEWARE: Ошибка импорта: {e}")
            except Exception as e:
                print(f"🔴 DEBUG MIDDLEWARE: Ошибка: {e}")
                import traceback
                traceback.print_exc()

        response = self.get_response(request)
        print(f"🟡 DEBUG MIDDLEWARE: Middleware завершен для {request.path}")
        return response