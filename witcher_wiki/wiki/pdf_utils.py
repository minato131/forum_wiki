import os
from django.conf import settings
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def register_custom_fonts():
    """Регистрирует кастомные шрифты с поддержкой кириллицы"""
    try:
        # Путь к шрифту DejaVuSans
        font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'DejaVuSans.ttf')

        if os.path.exists(font_path):
            # Регистрируем обычный шрифт
            pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))

            # Регистрируем жирный вариант (используем тот же файл, но указываем как bold)
            pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', font_path))

            # Регистрируем семейство
            pdfmetrics.registerFontFamily('DejaVuSans',
                                          normal='DejaVuSans',
                                          bold='DejaVuSans-Bold')

            return True
        else:
            print(f"Шрифт DejaVuSans не найден по пути: {font_path}")
            return False
    except Exception as e:
        print(f"Ошибка при регистрации шрифтов: {e}")
        return False


def wrap_text(text, font, font_size, max_width):
    """Разбивает текст на строки по ширине"""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    # Создаем временный canvas для измерения текста
    temp_buffer = io.BytesIO()
    temp_canvas = canvas.Canvas(temp_buffer, pagesize=A4)

    lines = []
    words = text.split()
    current_line = []

    for word in words:
        # Проверяем длину текущей строки с новым словом
        test_line = ' '.join(current_line + [word])
        width = temp_canvas.stringWidth(test_line, font, font_size)

        if width <= max_width:
            current_line.append(word)
        else:
            # Сохраняем текущую строку и начинаем новую
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]

    # Добавляем последнюю строку
    if current_line:
        lines.append(' '.join(current_line))

    return lines


def clean_html_for_pdf(html_content, max_length=None):
    """Очищает HTML контент для PDF"""
    import re

    if not html_content:
        return ""

    # Удаляем HTML теги
    clean = re.compile('<.*?>')
    text_only = re.sub(clean, '', html_content)

    # Заменяем HTML entities
    replacements = {
        '&nbsp;': ' ',
        '&amp;': '&',
        '&lt;': '<',
        '&gt;': '>',
        '&quot;': '"',
        '&#39;': "'",
        '&rsquo;': "'",
        '&lsquo;': "'",
        '&rdquo;': '"',
        '&ldquo;': '"',
        '&ndash;': '-',
        '&mdash;': '—',
        '&hellip;': '...',
    }

    for entity, replacement in replacements.items():
        text_only = text_only.replace(entity, replacement)

    # Декодируем Unicode entities
    def decode_unicode(match):
        try:
            code = int(match.group(1))
            return chr(code)
        except:
            return match.group(0)

    def decode_hex(match):
        try:
            code = int(match.group(1), 16)
            return chr(code)
        except:
            return match.group(0)

    text_only = re.sub(r'&#(\d+);', decode_unicode, text_only)
    text_only = re.sub(r'&#x([0-9a-fA-F]+);', decode_hex, text_only)

    # Удаляем лишние пробелы и переносы
    text_only = re.sub(r'\s+', ' ', text_only)
    text_only = re.sub(r'\n\s*\n', '\n\n', text_only)

    # Обрезаем если нужно
    if max_length and len(text_only) > max_length:
        text_only = text_only[:max_length - 3] + "..."

    return text_only.strip()