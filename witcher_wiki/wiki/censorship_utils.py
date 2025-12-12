# wiki/censorship_utils.py
from django.contrib import messages
from .censorship import CensorshipService


def check_request_for_banned_words(request):
    """Проверяет POST запрос на запрещенные слова"""
    if request.method != 'POST':
        return False, []

    banned_words_found = []

    for field_name, field_value in request.POST.items():
        if isinstance(field_value, str) and field_value.strip():
            has_banned, found_words, _ = CensorshipService.contains_banned_words(field_value)
            if has_banned:
                banned_words_found.extend(found_words)

    # Убираем дубликаты
    banned_words_found = list(set(banned_words_found))

    if banned_words_found:
        # Добавляем в request для использования в middleware и формах
        request.censorship_violation = True
        request.banned_words_found = banned_words_found

        # Логируем для админов
        if request.user.is_authenticated and request.user.is_staff:
            print(
                f"🔴 ЦЕНЗУРА: Админ {request.user.username} отправил запрещенные слова: {', '.join(banned_words_found[:3])}")

        return True, banned_words_found

    return False, []


def add_censorship_warning(request, banned_words):
    """Добавляет предупреждение о цензуре"""
    if banned_words:
        words_display = ', '.join(banned_words[:3])
        if len(banned_words) > 3:
            words_display += f' и еще {len(banned_words) - 3}...'

        messages.warning(
            request,
            f'⚠️ Обнаружена нецензурная лексика: {words_display}. '
            f'Пожалуйста, соблюдайте правила сообщества.'
        )