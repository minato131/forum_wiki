# wiki/moderation_views.py
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone

from .admin_forms import UserBanForm, UserWarningForm, UserSearchForm
from .moderation_service import ModerationService
from .models import ModerationLog


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
    ).order_by('-created_at')[:10]

    # Последние баны
    recent_bans = ModerationService.get_banned_users()[:5]

    # Пользователи с предупреждениями
    warned_users = ModerationService.get_users_with_warnings(min_warnings=1)[:5]

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
    from .models import UserBan
    ban_history = UserBan.objects.filter(user=user).order_by('-created_at')

    # История предупреждений
    from .models import UserWarning
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
                messages.success(request, f'Пользователь {user.username} забанен')
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
                messages.success(request, f'Пользователю {user.username} выдано предупреждение')
                return redirect('wiki:user_detail', user_id=user.id)
            else:
                # Если форма не валидна, показываем ошибки
                for field, errors in warning_form.errors.items():
                    for error in errors:
                        messages.error(request, f'Ошибка в поле "{field}": {error}')

        elif action == 'unban':
            success = ModerationService.unban_user(
                user=user,
                unbanned_by=request.user,
                reason=request.POST.get('unban_reason', '')
            )
            if success:
                messages.success(request, f'Пользователь {user.username} разбанен')
            else:
                messages.error(request, 'Не удалось разбанить пользователя')
            return redirect('wiki:user_detail', user_id=user.id)

        elif action == 'remove_warning':
            warning_id = request.POST.get('warning_id')
            if warning_id:
                success = ModerationService.remove_warning(
                    warning_id=warning_id,
                    removed_by=request.user,
                    reason=request.POST.get('remove_reason', '')
                )
                if success:
                    messages.success(request, 'Предупреждение снято')
                else:
                    messages.error(request, 'Предупреждение не найдено')
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
def warned_users_list(request):
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


@staff_required
def clear_old_logs(request):
    """Очистка старых логов"""
    if request.method == 'POST':
        month_ago = timezone.now() - timezone.timedelta(days=30)
        deleted_count, _ = ModerationLog.objects.filter(
            created_at__lt=month_ago
        ).delete()

        messages.success(request, f'Удалено {deleted_count} старых логов (старше 30 дней).')

    return redirect('wiki:moderation_logs')


@staff_required
def warn_user(request, user_id):
    """Выдать предупреждение пользователю (через отдельную форму)"""
    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        form = UserWarningForm(request.POST)
        if form.is_valid():
            warning = ModerationService.issue_warning(
                user=user,
                issued_by=request.user,
                severity=form.cleaned_data['severity'],
                reason=form.cleaned_data['reason'],
                related_content=form.cleaned_data.get('related_content', '')
            )
            # ДОБАВЬТЕ messages здесь
            messages.success(request, f'Предупреждение выдано пользователю {user.username}')
            return redirect('wiki:user_detail', user_id=user.id)
    else:
        form = UserWarningForm()

    return render(request, 'wiki/moderation/warn_user.html', {
        'user': user,
        'form': form,
    })


@staff_required
def ban_user(request, user_id):
    """Забанить пользователя (через отдельную форму)"""
    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        form = UserBanForm(request.POST)
        if form.is_valid():
            ban = ModerationService.ban_user(
                user=user,
                banned_by=request.user,
                reason=form.cleaned_data['reason'],
                duration=form.cleaned_data['duration'],
                notes=form.cleaned_data['notes']
            )
            # ДОБАВЬТЕ messages здесь
            messages.success(request, f'Пользователь {user.username} забанен')
            return redirect('wiki:banned_users_list')
    else:
        form = UserBanForm()

    return render(request, 'wiki/moderation/ban_user.html', {
        'user': user,
        'form': form,
    })

@staff_required
def unban_user(request, user_id):
    """Разбанить пользователя"""
    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        reason = request.POST.get('reason', 'Досрочное снятие бана')
        success = ModerationService.unban_user(
            user=user,
            unbanned_by=request.user,
            reason=reason
        )
        # ДОБАВЬТЕ messages здесь
        if success:
            messages.success(request, f'Пользователь {user.username} разбанен')
        else:
            messages.error(request, 'Не удалось разбанить пользователя')

    return redirect('wiki:banned_users_list')

@staff_required
def remove_warning(request, warning_id):
    """Удалить предупреждение"""
    from .models import UserWarning

    warning = get_object_or_404(UserWarning, id=warning_id)

    if request.method == 'POST':
        reason = request.POST.get('reason', 'Снятие предупреждения')
        ModerationService.remove_warning(
            warning_id=warning_id,
            removed_by=request.user,
            reason=reason
        )
        messages.success(request, 'Предупреждение удалено')

    return redirect('wiki:warned_users_list')


@staff_required
def remove_expired_ban(request, ban_id):
    """Удалить истекший бан"""
    from .models import UserBan

    ban = get_object_or_404(UserBan, id=ban_id)

    if request.method == 'POST':
        if ban.is_expired():
            ban.delete()
            ModerationService.create_moderation_log(
                moderator=request.user,
                target_user=ban.user,
                action_type='remove_expired_ban',
                details=f'Удален истекший бан #{ban.id}'
            )
            messages.success(request, 'Истекший бан удален')
        else:
            messages.error(request, 'Бан еще не истек')

    return redirect('wiki:banned_users_list')

