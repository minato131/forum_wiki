# wiki/moderation_service.py - исправленная версия
from django.utils import timezone
from django.contrib import messages
from django.core.cache import cache
from .models import UserBan, UserWarning, ModerationLog
from .censorship_warnings import CensorshipWarningSystem
from django.contrib.auth import get_user_model
User = get_user_model()


class ModerationService:
    """Сервис для управления модерацией"""

    @staticmethod
    def get_user_status(user):
        """Получает полный статус пользователя"""
        active_bans = UserBan.objects.filter(user=user, is_active=True)
        active_warnings = UserWarning.objects.filter(user=user, is_active=True)

        # Проверяем активные баны
        is_banned = False
        ban_details = None
        for ban in active_bans:
            if not ban.is_expired():
                is_banned = True
                ban_details = ban
                break
            else:
                ban.is_active = False
                ban.save()

        # Получаем предупреждения цензуры
        censorship_warnings = CensorshipWarningSystem.get_user_warnings(user)

        return {
            'user': user,
            'is_banned': is_banned,
            'ban_details': ban_details,
            'active_warnings': active_warnings.count(),
            'censorship_warnings': censorship_warnings,
            'total_warnings': active_warnings.count() + censorship_warnings,
            'can_post': not is_banned,
            'can_comment': not is_banned,
            'can_message': not is_banned,
        }

    @staticmethod
    def ban_user(user, banned_by, reason, duration, notes=''):
        """Банит пользователя"""
        # Снимаем старые активные баны
        UserBan.objects.filter(user=user, is_active=True).update(is_active=False)

        # Создаем новый бан
        ban = UserBan.objects.create(
            user=user,
            banned_by=banned_by,
            reason=reason,
            duration=duration,
            notes=notes
        )

        # Логируем действие
        ModerationLog.objects.create(
            moderator=banned_by,
            target_user=user,
            action_type='ban_issued',
            details={
                'reason': reason,
                'duration': duration,
                'ban_id': ban.id,
                'notes': notes,
                'message': f'Пользователь {user.username} забанен на {ban.get_duration_display()}',
            }
        )

        return ban

    @staticmethod
    def unban_user(user, unbanned_by, reason=''):
        """Разбанивает пользователя"""
        # Находим активные баны
        active_bans = UserBan.objects.filter(user=user, is_active=True)

        for ban in active_bans:
            ban.is_active = False
            ban.save()

            # Логируем действие
            ModerationLog.objects.create(
                moderator=unbanned_by,
                target_user=user,
                action_type='ban_removed',
                details={
                    'ban_id': ban.id,
                    'reason': reason,
                    'original_reason': ban.reason,
                    'original_duration': ban.duration,
                    'message': f'Бан пользователя {user.username} снят',
                }
            )

        return True

    @staticmethod
    def issue_warning(user, issued_by, severity, reason, related_content=''):
        """Выдает официальное предупреждение"""
        warning = UserWarning.objects.create(
            user=user,
            issued_by=issued_by,
            severity=severity,
            reason=reason,
            related_content=related_content
        )

        # Логируем действие
        ModerationLog.objects.create(
            moderator=issued_by,
            target_user=user,
            action_type='warning_issued',
            details={
                'warning_id': warning.id,
                'severity': severity,
                'reason': reason,
                'message': f'Пользователю {user.username} выдано предупреждение',
            }
        )

        return warning

    @staticmethod
    def remove_warning(warning_id, removed_by, reason=''):
        """Удаляет предупреждение"""
        try:
            warning = UserWarning.objects.get(id=warning_id)
            warning.is_active = False
            warning.save()

            # Логируем действие
            ModerationLog.objects.create(
                moderator=removed_by,
                target_user=warning.user,
                action_type='warning_removed',
                details={
                    'warning_id': warning.id,
                    'original_severity': warning.severity,
                    'original_reason': warning.reason,
                    'reason': reason,
                    'message': f'Предупреждение пользователя {warning.user.username} снято',
                }
            )

            return True
        except UserWarning.DoesNotExist:
            return False
    @staticmethod
    def get_banned_users():
        """Получает список забаненных пользователей"""
        banned_users = []

        for ban in UserBan.objects.filter(is_active=True).select_related('user', 'banned_by'):
            if not ban.is_expired():
                banned_users.append({
                    'user': ban.user,
                    'ban': ban,
                    'time_remaining': ban.time_remaining(),
                    'banned_by': ban.banned_by,
                    'reason': ban.get_reason_display(),
                })
            else:
                ban.is_active = False
                ban.save()

        return banned_users

    @staticmethod
    def get_users_with_warnings(min_warnings=1):
        """Получает пользователей с предупреждениями"""
        User = get_user_model()
        users_data = []

        for user in User.objects.filter(is_active=True):
            status = ModerationService.get_user_status(user)
            if status['total_warnings'] >= min_warnings:
                users_data.append({
                    'user': user,
                    'status': status,
                    'official_warnings': UserWarning.objects.filter(user=user, is_active=True),
                    'censorship_warnings': status['censorship_warnings'],
                })

        # Сортируем по количеству предупреждений
        users_data.sort(key=lambda x: x['status']['total_warnings'], reverse=True)

        return users_data

    @staticmethod
    def get_moderation_stats():
        """Получает статистику модерации"""
        total_users = User.objects.count()
        active_bans = len(ModerationService.get_banned_users())
        active_warnings = UserWarning.objects.filter(is_active=True).count()

        # Считаем предупреждения цензуры
        total_censorship_warnings = 0
        for user in User.objects.all():
            total_censorship_warnings += CensorshipWarningSystem.get_user_warnings(user)

        # Логи за последние 7 дней
        week_ago = timezone.now() - timezone.timedelta(days=7)
        recent_actions = ModerationLog.objects.filter(created_at__gte=week_ago).count()

        return {
            'total_users': total_users,
            'active_bans': active_bans,
            'active_warnings': active_warnings,
            'censorship_warnings': total_censorship_warnings,
            'recent_actions': recent_actions,
            'ban_rate': round((active_bans / total_users * 100), 2) if total_users > 0 else 0,
        }