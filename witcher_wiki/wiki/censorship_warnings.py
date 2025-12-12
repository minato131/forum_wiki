# wiki/censorship_warnings.py
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import json
from django.core.cache import cache


class CensorshipWarningSystem:
    """Система предупреждений за использование нецензурной лексики"""

    @staticmethod
    def get_user_warnings(user):
        """Получает количество предупреждений пользователя"""
        cache_key = f'censorship_warnings_{user.id}'
        warnings = cache.get(cache_key, 0)
        return warnings

    @staticmethod
    def add_user_warning(user, words_found):
        """Добавляет предупреждение пользователю"""
        cache_key = f'censorship_warnings_{user.id}'
        current_warnings = cache.get(cache_key, 0)
        new_warnings = current_warnings + 1

        # Сохраняем на 30 дней
        cache.set(cache_key, new_warnings, 60 * 60 * 24 * 30)

        # Логируем нарушение
        CensorshipWarningSystem._log_violation(user, words_found, new_warnings)

        return new_warnings

    @staticmethod
    def reset_user_warnings(user):
        """Сбрасывает предупреждения пользователя"""
        cache_key = f'censorship_warnings_{user.id}'
        cache.delete(cache_key)

    @staticmethod
    def get_warning_message(warning_count):
        """Возвращает сообщение в зависимости от количества предупреждений"""
        messages = {
            1: "🚫 Первое предупреждение: Обнаружена нецензурная лексика. Пожалуйста, соблюдайте правила сообщества.",
            2: "⚠️ Второе предупреждение: Продолжение использования нецензурной лексики может привести к временной блокировке.",
            3: "🔴 Третье предупреждение: Следующее нарушение приведет к блокировке аккаунта на 24 часа.",
            4: "⛔ Четвертое предупреждение: Ваш аккаунт будет заблокирован на 24 часа.",
        }

        if warning_count >= 5:
            return "🚨 Серьезное нарушение: Ваш аккаунт заблокирован. Обратитесь к администратору."

        return messages.get(warning_count, "Обнаружена нецензурная лексика. Пожалуйста, исправьте текст.")

    @staticmethod
    def get_punishment_level(warning_count):
        """Определяет уровень наказания"""
        if warning_count == 1:
            return "warning"
        elif warning_count == 2:
            return "warning_strong"
        elif warning_count == 3:
            return "warning_critical"
        elif warning_count == 4:
            return "temp_ban_1h"
        elif warning_count >= 5:
            return "temp_ban_24h"
        return "notice"

    @staticmethod
    def _log_violation(user, words_found, warning_count):
        """Логирует нарушение"""
        log_entry = {
            'user_id': user.id,
            'username': user.username,
            'timestamp': timezone.now().isoformat(),
            'words_found': words_found,
            'warning_count': warning_count,
            'ip_address': None,  # Можно добавить позже
        }

        # Сохраняем в лог (можно сохранять в БД или файл)
        cache_key = f'censorship_log_{user.id}_{int(timezone.now().timestamp())}'
        cache.set(cache_key, json.dumps(log_entry), 60 * 60 * 24 * 7)  # Храним неделю

        print(f"🔴 ЦЕНЗУРА ЛОГ: {user.username} - нарушение #{warning_count}. Слова: {', '.join(words_found)}")

    @staticmethod
    def handle_censorship_violation(request, banned_words):
        """Обрабатывает нарушение цензуры и возвращает сообщение"""
        if not request.user.is_authenticated:
            return "Анонимным пользователям запрещено использовать нецензурную лексику."

        # Добавляем предупреждение
        warning_count = CensorshipWarningSystem.add_user_warning(request.user, banned_words)

        # Получаем сообщение
        message = CensorshipWarningSystem.get_warning_message(warning_count)

        # Добавляем детали
        words_list = ', '.join(banned_words[:3])
        if len(banned_words) > 3:
            words_list += f' и еще {len(banned_words) - 3}...'

        full_message = f"{message}\n\nНарушение #{warning_count}: {words_list}"

        # Для админов добавляем статистику
        if request.user.is_staff:
            full_message += f"\n\n[АДМИН] Всего нарушений у пользователя: {warning_count}"

        return full_message