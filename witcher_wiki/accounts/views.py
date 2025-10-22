from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from wiki.models import UserProfile


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('wiki:home')
        else:
            messages.error(request, 'Неверное имя пользователя или пароль')

    return render(request, 'registration/login.html')


def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('wiki:home')
    else:
        form = UserCreationForm()

    return render(request, 'registration/register.html', {'form': form})


@login_required
def profile_view(request):
    # Получаем или создаем профиль пользователя
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        # Обработка загрузки аватарки
        if 'update_avatar' in request.POST and 'avatar' in request.FILES:
            user_profile.avatar = request.FILES['avatar']
            user_profile.save()
            messages.success(request, 'Аватар успешно обновлен!')
            return redirect('accounts:profile')  # Редирект для обновления страницы

        # Обработка обновления соцсетей
        elif 'update_profile' in request.POST:
            user_profile.telegram = request.POST.get('telegram', '')
            user_profile.vk = request.POST.get('vk', '')
            user_profile.youtube = request.POST.get('youtube', '')
            user_profile.discord = request.POST.get('discord', '')
            user_profile.bio = request.POST.get('bio', '')
            user_profile.save()
            messages.success(request, 'Профиль успешно обновлен!')
            return redirect('accounts:profile')  # Редирект для обновления страницы

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
        logout(request)
        messages.success(request, 'Вы успешно вышли из системы')
        return redirect('wiki:home')
    else:
        return redirect('wiki:home')