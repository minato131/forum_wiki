from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Q
from django.core.paginator import Paginator

from .admin_forms import UserBanForm, UserWarningForm, UserSearchForm
from .moderation_service import ModerationService


def staff_required(view_func):
    """Декоратор для проверки прав staff"""
    return user_passes_test(lambda u: u.is_staff)(view_func)


@staff_required
def moderation_dashboard(request):
    """Дашборд модерации"""
    stats = ModerationService.get_moderation_stats()

    # Последние действия
    recent_actions = ModerationLog.objects.all().select_related(
        'moderator', 'target_user'
    )[:10]

    # Последние баны
    recent_bans = ModerationService.get_banned_users()[:5]

    # Пользователи с предупреждениями
    warned_users = ModerationService.get_users_with_warnings(min_warnings=2)[:5]

    return render(request, 'wiki/moderation/dashboard.html', {
        'stats': stats,
        'recent_actions': recent_actions,
        'recent_bans': recent_bans,
        'warned_users': warned_users,
    })


@staff_required
def user_search(request):
    """Поиск пользователей для модерации"""
    form = UserSearchForm(request.GET or None)
    users = []

    if form.is_valid():
        username = form.cleaned_data.get('username')
        email = form.cleaned_data.get('email')
        has_warnings = form.cleaned_data.get('has_warnings')
        is_banned = form.cleaned_data.get('is_banned')

        # Базовый queryset
        queryset = User.objects.filter(is_active=True)

        # Применяем фильтры
        if username:
            queryset = queryset.filter(username__icontains=username)

        if email:
            queryset = queryset.filter(email__icontains=email)

        # Преобразуем queryset в список с доп. информацией
        for user in queryset[:50]:  # Ограничиваем для производительности
            user_status = ModerationService.get_user_status(user)

            # Применяем дополнительные фильтры
            if has_warnings and user_status['total_warnings'] == 0:
                continue

            if is_banned and not user_status['is_banned']:
                continue

            users.append({
                'user': user,
                'status': user_status,
            })

    return render(request, 'wiki/moderation/user_search.html', {
        'form': form,
        'users': users,
    })


@staff_required
def user_detail(request, user_id):
    """Детальная информация о пользователе"""
    user = get_object_or_404(User, id=user_id)
    user_status = ModerationService.get_user_status(user)

    # История банов
    ban_history = UserBan.objects.filter(user=user).order_by('-created_at')

    # История предупреждений
    warning_history = UserWarning.objects.filter(user=user).order_by('-created_at')

    # Формы для действий
    ban_form = UserBanForm()
    warning_form = UserWarningForm()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'ban':
            ban_form = UserBanForm(request.POST)
            if ban_form.is_valid():
                ModerationService.ban_user(
                    user=user,
                    banned_by=request.user,
                    reason=ban_form.cleaned_data['reason'],
                    duration=ban_form.cleaned_data['duration'],
                    notes=ban_form.cleaned_data['notes']
                )
                return redirect('wiki:user_detail', user_id=user.id)

        elif action == 'warning':
            warning_form = UserWarningForm(request.POST)
            if warning_form.is_valid():
                ModerationService.issue_warning(
                    user=user,
                    issued_by=request.user,
                    severity=warning_form.cleaned_data['severity'],
                    reason=warning_form.cleaned_data['reason'],
                    related_content=warning_form.cleaned_data['related_content']
                )
                return redirect('wiki:user_detail', user_id=user.id)

        elif action == 'unban':
            ModerationService.unban_user(
                user=user,
                unbanned_by=request.user,
                reason=request.POST.get('unban_reason', '')
            )
            return redirect('wiki:user_detail', user_id=user.id)

        elif action == 'remove_warning':
            warning_id = request.POST.get('warning_id')
            if warning_id:
                ModerationService.remove_warning(
                    warning_id=warning_id,
                    removed_by=request.user,
                    reason=request.POST.get('remove_reason', '')
                )
            return redirect('wiki:user_detail', user_id=user.id)

    return render(request, 'wiki/moderation/user_detail.html', {
        'target_user': user,
        'user_status': user_status,
        'ban_history': ban_history,
        'warning_history': warning_history,
        'ban_form': ban_form,
        'warning_form': warning_form,
    })


@staff_required
def banned_users_list(request):
    """Список забаненных пользователей"""
    banned_users = ModerationService.get_banned_users()

    # Пагинация
    paginator = Paginator(banned_users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'wiki/moderation/banned_users.html', {
        'page_obj': page_obj,
        'total_banned': len(banned_users),
    })


@staff_required
def warning_users_list(request):
    """Список пользователей с предупреждениями"""
    warned_users = ModerationService.get_users_with_warnings(min_warnings=1)

    # Пагинация
    paginator = Paginator(warned_users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'wiki/moderation/warned_users.html', {
        'page_obj': page_obj,
        'total_warned': len(warned_users),
    })


@staff_required
def moderation_logs(request):
    """Логи модерации"""
    logs = ModerationLog.objects.all().select_related(
        'moderator', 'target_user'
    ).order_by('-created_at')

    # Фильтры
    action_type = request.GET.get('action_type')
    moderator_id = request.GET.get('moderator')

    if action_type:
        logs = logs.filter(action_type=action_type)

    if moderator_id:
        logs = logs.filter(moderator_id=moderator_id)

    # Пагинация
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Доступные фильтры
    moderators = User.objects.filter(is_staff=True)

    return render(request, 'wiki/moderation/logs.html', {
        'page_obj': page_obj,
        'moderators': moderators,
        'action_types': ModerationLog.ACTION_TYPES,
        'selected_action': action_type,
        'selected_moderator': moderator_id,
    })