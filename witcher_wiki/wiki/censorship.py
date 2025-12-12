# wiki/censorship.py
import re
from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import escape


class CensorshipService:
    """Сервис для цензуры контента"""

    # Расширенный список запрещенных слов с учетом разных написаний
    BANNED_WORDS = [
        # ============== МАТ ==============
        # Основной мат
        'ху[йиыя]', 'п[иі]зд[ауео]', 'ёб[ау]', 'еб[ау]',
        'бля[дт]ь', 'бля', 'с[уy]к[аa]', 'пид[оo]р',
        'г[аa]нд[оo]н', 'м[уy]д[аaеe]к', 'х[уy][ёеe]',

        # Обходные варианты написания
        'х[уy][йий]', 'х[уy]й', 'х[уy]я', 'х[уy]и',
        'п[иiі]зд', 'п[иiі]зд[аaуy]', 'п[иiі]зд[еeоo]',
        'ёб', 'еб[аa]н', 'еб[аa]л', 'еб[аa]т[ьъ]',
        'бл[яa]д[ьъ]', 'бл[яa]', 'бл[яa]х',
        'с[уy]ч[аa]', 'с[уy]чк[аa]',
        'п[иi]д[аa]р', 'п[иi]др', 'п[иi]д[оo]р[аa]с',

        # ============== ГРУБЫЕ СЛОВА ==============
        'ж[оo]п[аa]', 'п[еe]н[иiі]с', 'в[аa]г[иi]н[аa]',
        'д[еe]б[иiі]л', 'д[аa]ун', '[уy]р[оo]д',
        'т[уy]п[оo][йий]', 'г[оo]вн[оo]',

        # ============== АНГЛИЙСКИЙ МАТ ==============
        'fuck', 'shit', 'bitch', 'asshole', 'dick', 'cock',
        'pussy', 'cunt', 'whore', 'slut',

        # ============== ОСКОРБЛЕНИЯ ==============
        'д[еe]бил', 'д[уy]р[аa]к', 'идиот', 'кретин',
        'м[оo]рд[аa]', 'р[оo]ж[аa]', 'урод',

        # ============== РАСИСТСКИЕ ВЫРАЖЕНИЯ ==============
        'ч[уy]рк[аa]', 'х[аa]ч', 'ч[уy]р[аa]', 'бл[яa]х',

        # ============== СЕКСУАЛЬНЫЕ ОСКОРБЛЕНИЯ ==============
        'шл[юy]х[аa]', 'бл[яa]д[ьъ]', 'пр[оo]ст[иi]т[уy]тк[аa]',
        'шмар[аa]', 'бл[яa]ш',
    ]

    # Слова, которые НЕ считаем матом (ложные срабатывания)
    WHITELIST = [
        'письмо', 'писал', 'писали', 'писать',
        'отправь', 'отправляй', 'отправил',
        'блять', 'блин', 'блинов',  # в контексте еды
        'сук', 'сукать',  # в контексте охоты
        'страхуй',  # в контексте страхования
        'перестрахуй', 'перестраховал',
        'писюн', 'писюнок',  # детские слова
    ]

    @classmethod
    def _prepare_pattern(cls, word):
        """Подготовка regex паттерна для слова"""
        # Заменяем русские буквы на варианты с латиницей
        replacements = {
            'а': '[аa@]', 'б': '[бb6]', 'в': '[вv]', 'г': '[гg]',
            'д': '[дd]', 'е': '[еeё]', 'ё': '[ёеe]', 'ж': '[жzh]',
            'з': '[зz3]', 'и': '[иi1]', 'й': '[йy]', 'к': '[кk]',
            'л': '[лl]', 'м': '[мm]', 'н': '[нn]', 'о': '[оo0]',
            'п': '[пp]', 'р': '[рr]', 'с': '[сc]', 'т': '[тt]',
            'у': '[уy]', 'ф': '[фf]', 'х': '[хx]', 'ц': '[цc]',
            'ч': '[чch]', 'ш': '[шsh]', 'щ': '[щsch]', 'ъ': '[ъ]',
            'ы': '[ыy]', 'ь': '[ь]', 'э': '[эe]', 'ю': '[юyu]',
            'я': '[яya]',
        }

        # Преобразуем слово в паттерн
        pattern = word.lower()
        for cyr, variants in replacements.items():
            pattern = pattern.replace(cyr, variants)

        # Добавляем возможные разделители между буквами
        pattern = r'[^\w]*'.join(list(pattern))

        # Добавляем границы слова
        return r'\b' + pattern + r'\b'

    @classmethod
    def contains_banned_words(cls, text):
        """
        Проверяет текст на наличие запрещенных слов.
        Возвращает (has_banned, found_words, positions)
        """
        if not text:
            return False, [], []

        text_lower = text.lower()
        found_words = []
        positions = []

        # Сначала проверяем белый список - если слово в белом списке, пропускаем
        for whitelist_word in cls.WHITELIST:
            if whitelist_word in text_lower:
                # Удаляем это слово из текста для проверки
                text_lower = text_lower.replace(whitelist_word, ' ' * len(whitelist_word))

        # Проверяем каждое запрещенное слово
        for banned_word in cls.BANNED_WORDS:
            pattern = re.compile(banned_word, re.IGNORECASE)
            matches = pattern.finditer(text)

            for match in matches:
                matched_word = match.group()

                # Проверяем, не является ли слово частью другого слова
                start, end = match.start(), match.end()

                # Проверяем границы слова
                if start > 0 and text[start - 1].isalnum():
                    continue
                if end < len(text) and text[end].isalnum():
                    continue

                found_words.append(matched_word)
                positions.append((start, end))

        return bool(found_words), found_words, positions

    @classmethod
    def filter_text(cls, text, replacement='[цензура]'):
        """
        Фильтрует текст, заменяя запрещенные слова.
        Возвращает (filtered_text, found_words)
        """
        if not text:
            return text, []

        has_banned, found_words, positions = cls.contains_banned_words(text)

        if not has_banned:
            return text, []

        # Сортируем позиции для правильной замены
        positions_sorted = sorted(zip(positions, found_words), key=lambda x: x[0][0])

        # Заменяем слова в тексте (с конца к началу, чтобы позиции не сбивались)
        filtered_text = text
        offset = 0

        for (start, end), word in positions_sorted:
            actual_start = start + offset
            actual_end = end + offset

            # Заменяем слово
            filtered_text = filtered_text[:actual_start] + replacement + filtered_text[actual_end:]

            # Обновляем смещение из-за разной длины замены
            offset += len(replacement) - (end - start)

        return filtered_text, list(set(found_words))  # Убираем дубликаты

    @classmethod
    def get_banned_words_count(cls):
        """Возвращает количество запрещенных слов в словаре"""
        return len(cls.BANNED_WORDS)


class CensorshipFormMixin:
    """Миксин для Django форм с проверкой цензуры"""

    def clean(self):
        cleaned_data = super().clean()

        # Проверяем все текстовые поля формы
        for field_name, field in self.fields.items():
            if self._is_text_field(field):
                if field_name in cleaned_data:
                    text = cleaned_data[field_name]
                    if text:
                        has_banned, found_words, _ = CensorshipService.contains_banned_words(text)

                        if has_banned:
                            self._raise_censorship_error(field_name, found_words)

        return cleaned_data

    def _is_text_field(self, field):
        """Определяет, является ли поле текстовым"""
        field_types = [
            forms.CharField,
            forms.TextField,
            forms.Textarea,
            forms.TextInput,
        ]

        # Проверяем тип поля
        for field_type in field_types:
            if isinstance(field, field_type):
                return True

        # Проверяем виджет
        widget_name = field.widget.__class__.__name__
        if widget_name in ['Textarea', 'TextInput', 'CKEditor5Widget']:
            return True

        return False

    def _raise_censorship_error(self, field_name, found_words):
        """Вызывает ошибку валидации для найденных запрещенных слов"""
        # Ограничиваем количество показываемых слов
        display_words = found_words[:3]
        words_display = ', '.join(display_words)

        if len(found_words) > 3:
            words_display += f' и еще {len(found_words) - 3}...'

        raise ValidationError({
            field_name: ValidationError(
                f'🚫 Обнаружена нецензурная лексика: {words_display}. '
                f'Пожалуйста, удалите оскорбительные выражения из текста.',
                code='censorship_violation'
            )
        })


class CensorshipAdminMixin:
    """Миксин для админ-панели с проверкой цензуры"""

    def save_model(self, request, obj, form, change):
        """Проверяем цензуру перед сохранением в админке"""
        text_fields = self._get_text_fields(obj)

        for field_name, field_value in text_fields:
            if field_value:
                has_banned, found_words, _ = CensorshipService.contains_banned_words(str(field_value))

                if has_banned:
                    # Логируем попытку
                    self.message_user(
                        request,
                        f'⚠️ В поле "{field_name}" обнаружена нецензурная лексика: {", ".join(found_words[:3])}',
                        level='WARNING'
                    )

                    # Автоматически фильтруем текст
                    filtered_text, _ = CensorshipService.filter_text(str(field_value))
                    setattr(obj, field_name, filtered_text)

        super().save_model(request, obj, form, change)

    def _get_text_fields(self, obj):
        """Возвращает список текстовых полей модели"""
        text_fields = []

        for field in obj._meta.get_fields():
            if hasattr(field, 'get_internal_type'):
                field_type = field.get_internal_type()
                if field_type in ['CharField', 'TextField']:
                    field_name = field.name
                    if hasattr(obj, field_name):
                        field_value = getattr(obj, field_name)
                        if field_value:
                            text_fields.append((field_name, field_value))

        return text_fields


# Утилиты для использования в представлениях
def censor_text(text):
    """Простая функция для цензуры текста"""
    return CensorshipService.filter_text(text)[0]


def check_text_for_banned_words(text):
    """Проверка текста на запрещенные слова"""
    return CensorshipService.contains_banned_words(text)