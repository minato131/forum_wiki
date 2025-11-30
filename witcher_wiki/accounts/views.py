from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from wiki.models import UserProfile

# ДОБАВИМ ИМПОРТЫ ДЛЯ ЛОГИРОВАНИЯ
from wiki.logging_utils import ActionLogger, log_user_login, log_user_logout


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # ЛОГИРОВАНИЕ: Успешный вход
            log_user_login(request)

            # Дополнительное логирование с деталями
            ActionLogger.log_action(
                request=request,
                action_type='login',
                description=f'Пользователь {user.username} вошел в систему',
                extra_data={
                    'login_method': 'standard',
                    'username': username,
                    'ip_address': ActionLogger.get_client_ip(request),
                }
            )

            messages.success(request, f'Добро пожаловать, {user.username}!')
            return redirect('wiki:home')
        else:
            # ЛОГИРОВАНИЕ: Неудачная попытка входа
            ActionLogger.log_action(
                request=request,
                action_type='login_failed',
                description=f'Неудачная попытка входа для пользователя {username}',
                extra_data={
                    'username': username,
                    'ip_address': ActionLogger.get_client_ip(request),
                }
            )

            messages.error(request, 'Неверное имя пользователя или пароль')

    return render(request, 'registration/login.html')


def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Создаем профиль пользователя
            UserProfile.objects.get_or_create(user=user)

            # ЛОГИРОВАНИЕ: Регистрация нового пользователя
            ActionLogger.log_action(
                request=request,
                action_type='user_register',
                description=f'Зарегистрирован новый пользователь {user.username}',
                target_object=user,
                extra_data={
                    'username': user.username,
                    'email': user.email if hasattr(user, 'email') else 'Не указан',
                    'ip_address': ActionLogger.get_client_ip(request),
                }
            )

            login(request, user)

            # ЛОГИРОВАНИЕ: Автоматический вход после регистрации
            ActionLogger.log_action(
                request=request,
                action_type='login',
                description=f'Пользователь {user.username} автоматически вошел после регистрации',
                extra_data={
                    'login_method': 'after_registration',
                }
            )

            messages.success(request, f'✅ Аккаунт создан! Добро пожаловать, {user.username}!')
            return redirect('wiki:home')
        else:
            # ЛОГИРОВАНИЕ: Ошибка регистрации
            ActionLogger.log_action(
                request=request,
                action_type='register_failed',
                description='Неудачная попытка регистрации',
                extra_data={
                    'form_errors': form.errors,
                    'ip_address': ActionLogger.get_client_ip(request),
                }
            )
    else:
        form = UserCreationForm()

    return render(request, 'registration/register.html', {'form': form})


@login_required
def profile_view(request):
    # Получаем или создаем профиль пользователя
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)

    # ЛОГИРОВАНИЕ: Просмотр профиля
    ActionLogger.log_action(
        request=request,
        action_type='profile_view',
        description=f'Пользователь {request.user.username} просматривает свой профиль',
        target_object=user_profile
    )

    if request.method == 'POST':
        # Обработка загрузки аватарки
        if 'update_avatar' in request.POST and 'avatar' in request.FILES:
            user_profile.avatar = request.FILES['avatar']
            user_profile.save()

            # ЛОГИРОВАНИЕ: Обновление аватара
            ActionLogger.log_action(
                request=request,
                action_type='profile_update',
                description=f'Пользователь {request.user.username} обновил аватар',
                target_object=user_profile,
                extra_data={
                    'update_type': 'avatar',
                    'avatar_file': request.FILES['avatar'].name,
                }
            )

            messages.success(request, '✅ Аватар успешно обновлен!')
            return redirect('accounts:profile')

        # Обработка обновления соцсетей
        elif 'update_profile' in request.POST:
            old_telegram = user_profile.telegram
            old_vk = user_profile.vk
            old_youtube = user_profile.youtube
            old_discord = user_profile.discord
            old_bio = user_profile.bio

            user_profile.telegram = request.POST.get('telegram', '')
            user_profile.vk = request.POST.get('vk', '')
            user_profile.youtube = request.POST.get('youtube', '')
            user_profile.discord = request.POST.get('discord', '')
            user_profile.bio = request.POST.get('bio', '')
            user_profile.save()

            # ЛОГИРОВАНИЕ: Обновление профиля
            changes = []
            if old_telegram != user_profile.telegram:
                changes.append('Telegram')
            if old_vk != user_profile.vk:
                changes.append('VK')
            if old_youtube != user_profile.youtube:
                changes.append('YouTube')
            if old_discord != user_profile.discord:
                changes.append('Discord')
            if old_bio != user_profile.bio:
                changes.append('биографию')

            ActionLogger.log_action(
                request=request,
                action_type='profile_update',
                description=f'Пользователь {request.user.username} обновил профиль: {", ".join(changes) if changes else "нет изменений"}',
                target_object=user_profile,
                extra_data={
                    'update_type': 'profile_info',
                    'changes': changes,
                }
            )

            messages.success(request, '✅ Профиль успешно обновлен!')
            return redirect('accounts:profile')

    # Упрощенная версия без импорта других моделей wiki
    context = {
        'user_articles_count': 0,
        'liked_articles_count': 0,
        'total_views': 0,
        'recent_articles': []
    }
    return render(request, 'accounts/profile.html', context)


def logout_view(request):
    if request.method == 'POST':
        # ЛОГИРОВАНИЕ перед выходом (пока пользователь еще аутентифицирован)
        if request.user.is_authenticated:
            log_user_logout(request)

            # Дополнительное логирование
            ActionLogger.log_action(
                request=request,
                action_type='logout',
                description=f'Пользователь {request.user.username} вышел из системы',
                extra_data={
                    'ip_address': ActionLogger.get_client_ip(request),
                }
            )

        logout(request)
        messages.success(request, '✅ Вы успешно вышли из системы')
        return redirect('wiki:home')
    else:
        # ЛОГИРОВАНИЕ: Попытка выхода не через POST
        if request.user.is_authenticated:
            ActionLogger.log_action(
                request=request,
                action_type='logout_attempt',
                description=f'Пользователь {request.user.username} попытался выйти не через POST-запрос',
                extra_data={
                    'method': request.method,
                }
            )

        return redirect('wiki:home')