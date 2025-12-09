from django.shortcuts import redirect
from rest_framework.generics import get_object_or_404

from .models import Article, Category, Comment, UserProfile, ArticleMedia, ModerationComment, ArticleRevision
from .models import AuthCode
from django.contrib.auth.models import Group
from django.contrib import admin
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from .permissions import GROUP_PERMISSIONS
from django.contrib import admin
from django.utils.html import format_html
from .models import ActionLog
import json
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from django.utils import timezone
from datetime import datetime, timedelta
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from .models import Backup
from django.utils import timezone
from django.utils.html import format_html
import os
from django.conf import settings
from .models import Backup
from django.urls import reverse
import os

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'created_at']
    list_filter = ['parent', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'status', 'created_at', 'views_count']
    list_filter = ['status', 'categories', 'created_at', 'author']
    search_fields = ['title', 'content', 'excerpt']
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ['categories']
    readonly_fields = ['views_count', 'created_at', 'updated_at']

    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'slug', 'excerpt', 'content', 'featured_image')
        }),
        ('Категоризация', {
            'fields': ('categories', 'tags')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
        ('Публикация', {
            'fields': ('author', 'status', 'published_at')
        }),
        ('Статистика', {
            'fields': ('views_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(ArticleRevision)
class ArticleRevisionAdmin(admin.ModelAdmin):
    list_display = ['article', 'author', 'created_at', 'comment']
    list_filter = ['created_at', 'author']
    search_fields = ['article__title', 'comment']
    readonly_fields = ['created_at']

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['article', 'author', 'created_at', 'is_approved']
    list_filter = ['is_approved', 'created_at']
    search_fields = ['content', 'article__title', 'author__username']
    actions = ['approve_comments', 'disapprove_comments']

    def approve_comments(self, request, queryset):
        queryset.update(is_approved=True)
    approve_comments.short_description = "Одобрить выбранные комментарии"

    def disapprove_comments(self, request, queryset):
        queryset.update(is_approved=False)
    disapprove_comments.short_description = "Отклонить выбранные комментарии"

def create_groups(sender, **kwargs):
    groups = ['Модератор', 'Редактор', 'Пользователь']
    for group_name in groups:
        Group.objects.get_or_create(name=group_name)

# Регистрируем сигнал
from django.db.models.signals import post_migrate
post_migrate.connect(create_groups)

admin.site.register(UserProfile)
admin.site.register(ArticleMedia)
admin.site.register(ModerationComment)

@admin.register(AuthCode)
class AuthCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'telegram_username', 'telegram_id', 'is_used', 'created_at']
    list_filter = ['is_used', 'created_at']
    search_fields = ['code', 'telegram_username']
    readonly_fields = ['created_at']


class CustomGroupAdmin(BaseGroupAdmin):
    """Кастомная админка для групп с описанием прав"""

    list_display = ['name', 'get_permissions_description', 'user_count']
    list_filter = ['name']

    def get_permissions_description(self, obj):
        """Возвращает описание прав для группы"""
        group_info = GROUP_PERMISSIONS.get(obj.name, {})
        return group_info.get('description', 'Нет описания')

    get_permissions_description.short_description = 'Описание прав'

    def user_count(self, obj):
        """Количество пользователей в группе"""
        return obj.user_set.count()

    user_count.short_description = 'Количество пользователей'

    def get_fieldsets(self, request, obj=None):
        """Добавляем описание прав в форму редактирования группы"""
        fieldsets = super().get_fieldsets(request, obj)

        if obj and obj.name in GROUP_PERMISSIONS:
            group_info = GROUP_PERMISSIONS[obj.name]
            description = f"""
            <div style="background: #f8f9fa; padding: 15px; border-left: 4px solid #007cba; margin-bottom: 20px;">
                <h3 style="margin-top: 0;">Права группы "{obj.name}"</h3>
                <p><strong>Описание:</strong> {group_info['description']}</p>
                <p><strong>Доступные права:</strong></p>
                <ul style="margin-bottom: 0;">
                    {''.join([f'<li>{perm}</li>' for perm in group_info['permissions']])}
                </ul>
            </div>
            """

            # Добавляем описание перед формой
            from django.utils.safestring import mark_safe
            self.description = mark_safe(description)

        return fieldsets


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    """Админ-панель для логов действий"""

    list_display = [
        'created_at',
        'user_info',
        'action_type_display',
        'description_short',
        'ip_address',
        'browser_short'
    ]

    list_filter = [
        'action_type',
        'created_at',
        'user',
    ]

    search_fields = [
        'user__username',
        'description',
        'ip_address',
        'action_data'
    ]

    readonly_fields = [
        'created_at',
        'user',
        'action_type',
        'description',
        'ip_address',
        'user_agent',
        'browser',
        'operating_system',
        'action_data_prettified',
        'target_object_link'
    ]

    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    actions = ['export_as_json', 'export_as_pdf', 'export_as_csv']
    def user_info(self, obj):
        if obj.user:
            return obj.user.username
        return 'Аноним'

    user_info.short_description = 'Пользователь'

    def action_type_display(self, obj):
        return obj.get_action_type_display()

    action_type_display.short_description = 'Тип действия'

    def description_short(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description

    description_short.short_description = 'Описание'

    def browser_short(self, obj):
        return obj.browser[:30] + '...' if len(obj.browser) > 30 else obj.browser

    browser_short.short_description = 'Браузер'

    def action_data_prettified(self, obj):
        """Красивое отображение JSON данных"""
        if obj.action_data:
            return format_html(
                '<pre style="background: #f5f5f5; padding: 10px; border-radius: 5px; overflow-x: auto;">{}</pre>',
                json.dumps(obj.action_data, ensure_ascii=False, indent=2)
            )
        return '-'

    action_data_prettified.short_description = 'Данные действия'

    def target_object_link(self, obj):
        """Ссылка на связанный объект если есть"""
        target = obj.get_target_object()
        if target:
            if hasattr(target, 'get_absolute_url'):
                return format_html(
                    '<a href="{}" target="_blank">{}</a>',
                    target.get_absolute_url(),
                    str(target)
                )
            return str(target)
        return '-'

    target_object_link.short_description = 'Связанный объект'

    # Отключаем возможность добавления/изменения логов через админку
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    # Группируем поля в админке
    fieldsets = (
        ('Основная информация', {
            'fields': ('created_at', 'user', 'action_type', 'description')
        }),
        ('Информация о клиенте', {
            'fields': ('ip_address', 'browser', 'operating_system', 'user_agent')
        }),
        ('Дополнительные данные', {
            'fields': ('action_data_prettified', 'target_object_link')
        }),
    )

    def export_as_json(self, request, queryset):
        """Экспорт выбранных логов в JSON"""
        logs_data = []
        for log in queryset:
            logs_data.append({
                'id': log.id,
                'user': log.user.username if log.user else 'Аноним',
                'action_type': log.action_type,
                'action_type_display': log.get_action_type_display(),
                'description': log.description,
                'ip_address': log.ip_address,
                'browser': log.browser,
                'operating_system': log.operating_system,
                'action_data': log.action_data,
                'created_at': log.created_at.isoformat(),
            })

        response = HttpResponse(
            json.dumps(logs_data, ensure_ascii=False, indent=2),
            content_type='application/json; charset=utf-8'
        )
        response['Content-Disposition'] = 'attachment; filename="action_logs.json"'
        return response

    export_as_json.short_description = "📄 Экспорт выбранных логов в JSON"

    def export_as_pdf(self, request, queryset):
        """Экспорт выбранных логов в PDF с поддержкой кириллицы"""

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="action_logs.pdf"'

        # Используем BytesIO для работы в памяти
        buffer = BytesIO()

        # Регистрация кириллического шрифта - КЛЮЧЕВОЙ МОМЕНТ!
        try:
            # Попробуем разные пути к шрифтам
            font_paths = [
                os.path.join(os.path.dirname(__file__), '..', 'static', 'fonts', 'Arial.ttf'),
                '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf',
                'C:/Windows/Fonts/arial.ttf',
            ]

            font_registered = False
            for font_path in font_paths:
                if os.path.exists(font_path):
                    pdfmetrics.registerFont(TTFont('Arial', font_path))
                    pdfmetrics.registerFont(TTFont('Arial-Bold', font_path.replace('Arial.ttf', 'Arial_Bold.ttf')))
                    font_registered = True
                    break

            if not font_registered:
                # Попробуем использовать DejaVu (часто уже установлен)
                try:
                    pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
                    font_name = 'DejaVuSans'
                    font_registered = True
                except:
                    font_name = 'Helvetica'
            else:
                font_name = 'Arial'

        except Exception as e:
            font_name = 'Helvetica'
            print(f"Ошибка регистрации шрифта: {e}")

        # Создаем документ
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )

        elements = []
        styles = getSampleStyleSheet()

        # Создаем стиль с нашим шрифтом
        if font_name != 'Helvetica':
            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontName=font_name,
                fontSize=9,
                encoding='UTF-8'
            )
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Title'],
                fontName=font_name + '-Bold' if font_name != 'DejaVuSans' else 'DejaVuSans-Bold',
                fontSize=14,
                spaceAfter=20,
                encoding='UTF-8'
            )
        else:
            normal_style = styles['Normal']
            normal_style.fontSize = 9
            title_style = styles['Title']
            title_style.fontSize = 14
            title_style.spaceAfter = 20

        # Заголовок
        title = Paragraph("Журнал действий пользователей", title_style)
        elements.append(title)
        elements.append(Spacer(1, 12))

        # Добавляем информацию о количестве записей
        count_info = Paragraph(f"Всего записей: {queryset.count()}", normal_style)
        elements.append(count_info)
        elements.append(Spacer(1, 20))

        # Данные для таблицы
        data = [['Дата', 'Пользователь', 'Тип действия', 'Описание', 'IP']]

        # Определяем ширины колонок (в процентах от ширины страницы)
        col_widths = [80, 60, 70, 200, 60]  # в пунктах

        # Заполняем данные
        for log in queryset:
            data.append([
                Paragraph(log.created_at.strftime('%d.%m.%Y<br/>%H:%M'), normal_style),
                Paragraph(log.user.username if log.user else 'Аноним', normal_style),
                Paragraph(log.get_action_type_display(), normal_style),
                Paragraph(log.description[:80] + '...' if len(log.description) > 80 else log.description, normal_style),
                Paragraph(log.ip_address or '-', normal_style)
            ])

        # Создаем таблицу с фиксированными ширинами
        table = Table(data, colWidths=col_widths, repeatRows=1)

        # Стили таблицы
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), font_name + '-Bold' if font_name != 'Helvetica' else 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),

            # Стиль для данных
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), font_name),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),

            # Границы
            ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),

            # Выравнивание
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Дата по центру
            ('ALIGN', (4, 1), (4, -1), 'CENTER'),  # IP по центру
            ('WORDWRAP', (3, 0), (3, -1), 'CJK'),  # Перенос слов в описании
        ])

        table.setStyle(table_style)
        elements.append(table)

        # Строим PDF
        doc.build(elements)

        # Получаем PDF из буфера
        pdf = buffer.getvalue()
        buffer.close()

        response.write(pdf)
        return response

    export_as_pdf.short_description = "📊 Экспорт выбранных логов в PDF"

    # Добавляем фильтры по дате
    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Фильтр по периоду
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

        if date_from:
            qs = qs.filter(created_at__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__lte=date_to)

        return qs

    def changelist_view(self, request, extra_context=None):
        # Добавляем форму фильтрации по дате
        extra_context = extra_context or {}
        extra_context['date_from'] = request.GET.get('date_from', '')
        extra_context['date_to'] = request.GET.get('date_to', '')
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(Backup)
class BackupAdmin(admin.ModelAdmin):
    """Админ-панель для управления резервными копиями"""

    list_display = ['name', 'backup_type_display', 'status_display', 'created_at', 'file_size_display',
                    'backup_actions']
    list_filter = ['backup_type', 'status', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['name', 'file_path', 'file_size', 'metadata_prettified', 'created_at']

    # Убираем стандартные actions - они нам не нужны
    actions = None

    # Используем кастомный шаблон с формой выбора даты
    change_list_template = 'admin/wiki/backup/change_list.html'

    def backup_type_display(self, obj):
        return obj.get_backup_type_display()

    backup_type_display.short_description = 'Тип'

    def status_display(self, obj):
        colors = {
            'completed': 'green',
            'in_progress': 'orange',
            'failed': 'red'
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_status_display()
        )

    status_display.short_description = 'Статус'

    def file_size_display(self, obj):
        return obj.file_size_display()

    file_size_display.short_description = 'Размер'

    def metadata_prettified(self, obj):
        if obj.metadata:
            return format_html(
                '<pre style="background: #f5f5f5; padding: 10px; border-radius: 5px; overflow-x: auto;">{}</pre>',
                json.dumps(obj.metadata, indent=2, ensure_ascii=False)
            )
        return '-'

    metadata_prettified.short_description = 'Метаданные'

    def backup_actions(self, obj):
        """Действия для резервных копий"""
        if obj.status == 'completed':
            download_url = reverse('admin:wiki_backup_download', args=[obj.id])
            return format_html(
                '''
                <div style="display: flex; gap: 5px;">
                    <a href="{}" class="button" title="Скачать" style="background: #4CAF50; color: white; padding: 5px 10px; border-radius: 3px; text-decoration: none; font-size: 12px;">
                        <i class="fas fa-download"></i> Скачать
                    </a>
                </div>
                ''',
                download_url
            )
        return '-'

    backup_actions.short_description = 'Действия'

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        """Добавляем кастомные URL для создания бэкапов"""
        urls = super().get_urls()
        from django.urls import path
        from django.contrib.admin.views.decorators import staff_member_required

        custom_urls = [
            path('create-backup/', staff_member_required(self.create_backup_view), name='wiki_backup_create'),
            path('<int:backup_id>/download/', staff_member_required(self.download_backup_view),
                 name='wiki_backup_download'),
            path('download-immediate/', staff_member_required(self.download_immediate_backup),
                 name='wiki_backup_download_immediate'),
        ]
        return custom_urls + urls

    def create_backup_view(self, request):
        """Создание бэкапа через админку - СКАЧИВАНИЕ В БРАУЗЕР"""
        from django.http import HttpResponse
        from io import BytesIO
        import zipfile
        import json
        from django.core import serializers
        from django.db import connection
        from django.utils import timezone
        from datetime import datetime

        if request.method == 'POST':
            backup_type = request.POST.get('backup_type', 'full')
            start_date = request.POST.get('start_date', '')
            end_date = request.POST.get('end_date', '')
            description = request.POST.get('description', '')

            try:
                # Определяем имя файла
                timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                if start_date and end_date:
                    filename = f'witcher_forum_backup_{start_date}_to_{end_date}_{timestamp}.zip'
                    description_text = f"{description} (период: {start_date} - {end_date})"
                else:
                    filename = f'witcher_forum_backup_{timestamp}.zip'
                    description_text = description

                # Создаем бэкап в памяти
                memory_file = BytesIO()

                with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    # БАЗА ДАННЫХ - получаем все данные
                    from .models import Article, Category, Comment, UserProfile, Message, SearchQuery

                    backup_data = {}
                    models_to_backup = [
                        ('articles', Article.objects.all()),
                        ('categories', Category.objects.all()),
                        ('comments', Comment.objects.filter(is_approved=True)),
                        ('profiles', UserProfile.objects.all()),
                        ('messages', Message.objects.all()),
                        ('search_queries', SearchQuery.objects.all()),
                    ]

                    # Фильтруем по датам если нужно
                    if start_date or end_date:
                        filtered_models = []
                        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None
                        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None

                        for model_name, queryset in models_to_backup:
                            if model_name == 'articles':
                                if start_date_obj:
                                    queryset = queryset.filter(created_at__date__gte=start_date_obj)
                                if end_date_obj:
                                    queryset = queryset.filter(created_at__date__lte=end_date_obj)
                            elif model_name in ['comments', 'messages']:
                                if start_date_obj:
                                    queryset = queryset.filter(created_at__date__gte=start_date_obj)
                                if end_date_obj:
                                    queryset = queryset.filter(created_at__date__lte=end_date_obj)

                            backup_data[model_name] = json.loads(
                                serializers.serialize('json', queryset)
                            )
                    else:
                        for model_name, queryset in models_to_backup:
                            backup_data[model_name] = json.loads(
                                serializers.serialize('json', queryset)
                            )

                    # Добавляем данные в JSON
                    backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2)
                    zipf.writestr('backup_data.json', backup_json)

                    # Добавляем метаданные
                    metadata = {
                        'created_at': timezone.now().isoformat(),
                        'backup_type': backup_type,
                        'description': description_text,
                        'total_articles': Article.objects.count(),
                        'total_categories': Category.objects.count(),
                        'total_users': UserProfile.objects.count(),
                        'total_comments': Comment.objects.count(),
                        'period_start': start_date,
                        'period_end': end_date,
                        'format_version': '1.0',
                        'generated_by': request.user.username,
                    }
                    zipf.writestr('metadata.json', json.dumps(metadata, indent=2))

                    # Экспорт SQL (опционально)
                    try:
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
                            tables = cursor.fetchall()

                        sql_dump = "-- SQL Dump - Форум Ведьмак\n"
                        sql_dump += f"-- Создано: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        sql_dump += f"-- Пользователь: {request.user.username}\n"
                        sql_dump += "-- =========================================\n\n"

                        for table_info in tables:
                            table_name = table_info[0]
                            sql_dump += f"\n-- Таблица: {table_name}\n"

                            # Получаем структуру таблицы
                            cursor.execute(f"PRAGMA table_info({table_name})")
                            columns_info = cursor.fetchall()

                            # Получаем данные
                            cursor.execute(f"SELECT * FROM {table_name} LIMIT 1000")  # Ограничиваем для больших таблиц
                            rows = cursor.fetchall()

                            if rows:
                                for row in rows:
                                    values = []
                                    for i, value in enumerate(row):
                                        if value is None:
                                            values.append('NULL')
                                        elif isinstance(value, str):
                                            # Экранируем кавычки
                                            values.append(f"'{value.replace(\"'\", \"''\")}'")
                                            elif isinstance(value, (int, float)):
                                            values.append(str(value))
                                            elif isinstance(value, bytes):
                                            # Для BLOB полей
                                            values.append(f"X'{value.hex()}'")
                                            else:
                                            values.append(f"'{str(value)}'")

                                            column_names = [col[1] for col in columns_info]
                                            sql_dump += f"INSERT INTO {table_name} ({', '.join(column_names)}) VALUES ({', '.join(values)});\n"
                                            else:
                                            sql_dump += f"-- Таблица {table_name} пуста\n"

                                            zipf.writestr('database_dump.sql', sql_dump)
                    except Exception as sql_error:
                        print(f"Ошибка экспорта SQL: {sql_error}")
                        zipf.writestr('database_dump.sql', f'-- Ошибка экспорта SQL: {sql_error}')

                memory_file.seek(0)

                # Возвращаем файл для скачивания
                response = HttpResponse(memory_file, content_type='application/zip')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                response['Content-Length'] = len(memory_file.getvalue())

                # Создаем запись в логах
                from .models import ActionLog
                ActionLog.objects.create(
                    user=request.user,
                    action_type='backup_download',
                    description=f'Скачан бэкап: {filename}',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    browser=request.META.get('HTTP_USER_AGENT', '')[:255],
                    action_data=metadata
                )

                return response

            except Exception as e:
                self.message_user(request, f'❌ Ошибка создания бэкапа: {str(e)}', level='error')
                import traceback
                traceback.print_exc()
                return redirect('admin:wiki_backup_changelist')

        # GET запрос - показываем форму
        from django.shortcuts import render
        from datetime import date, timedelta

        today = date.today()
        dates_list = []
        for i in range(30):
            current_date = today - timedelta(days=i)
            dates_list.append(current_date)

        context = {
            'title': 'Создание резервной копии',
            'dates_list': dates_list,
            'today': today,
            'week_ago': today - timedelta(days=7),
        }
        return render(request, 'admin/wiki/backup/create_backup.html', context)

    def download_backup_view(self, request, backup_id):
        """Скачивание существующего бэкапа - ИЗМЕНЕНО ДЛЯ СКАЧИВАНИЯ"""
        from django.shortcuts import get_object_or_404
        from django.http import HttpResponse

        backup = get_object_or_404(Backup, id=backup_id)

        if backup.file_path and os.path.exists(backup.file_path):
            with open(backup.file_path, 'rb') as f:
                file_data = f.read()

            response = HttpResponse(file_data, content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{backup.name}.zip"'
            response['Content-Length'] = len(file_data)

            # Логируем скачивание
            from .models import ActionLog
            ActionLog.objects.create(
                user=request.user,
                action_type='backup_download_existing',
                description=f'Скачан существующий бэкап: {backup.name}',
                ip_address=request.META.get('REMOTE_ADDR'),
                browser=request.META.get('HTTP_USER_AGENT', '')[:255]
            )

            return response
        else:
            # Если файла нет на сервере, создаем новый для скачивания
            return self.download_immediate_backup(request)

    def download_immediate_backup(self, request):
        """Немедленное создание и скачивание бэкапа"""
        from django.http import HttpResponse
        from io import BytesIO
        import zipfile
        import json
        from django.core import serializers
        from django.utils import timezone

        try:
            # Создаем бэкап в памяти
            memory_file = BytesIO()
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f'witcher_forum_backup_immediate_{timestamp}.zip'

            with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Получаем данные
                from .models import Article, Category, Comment, UserProfile, Message, SearchQuery

                backup_data = {}
                models_to_backup = [
                    ('articles', Article.objects.all()),
                    ('categories', Category.objects.all()),
                    ('comments', Comment.objects.filter(is_approved=True)),
                    ('profiles', UserProfile.objects.all()),
                    ('messages', Message.objects.all()),
                    ('search_queries', SearchQuery.objects.all()),
                ]

                for model_name, queryset in models_to_backup:
                    backup_data[model_name] = json.loads(
                        serializers.serialize('json', queryset)
                    )

                # Основной файл с данными
                backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2)
                zipf.writestr('backup_data.json', backup_json)

                # Метаданные
                metadata = {
                    'created_at': timezone.now().isoformat(),
                    'backup_type': 'immediate',
                    'description': 'Немедленный бэкап из админки',
                    'total_articles': Article.objects.count(),
                    'total_categories': Category.objects.count(),
                    'total_users': UserProfile.objects.count(),
                    'total_comments': Comment.objects.count(),
                    'format_version': '1.0',
                    'generated_by': request.user.username,
                }
                zipf.writestr('metadata.json', json.dumps(metadata, indent=2))

                # Простой отчет в TXT
                report = f"""ОТЧЕТ ПО БЭКАПУ
    ========================
    Форум: Вселенная Ведьмака
    Дата создания: {timezone.now().strftime('%d.%m.%Y %H:%M:%S')}
    Создал: {request.user.username}

    СТАТИСТИКА:
    • Статей: {Article.objects.count()}
    • Категорий: {Category.objects.count()}
    • Пользователей: {UserProfile.objects.count()}
    • Комментариев: {Comment.objects.count()}
    • Сообщений: {Message.objects.count()}
    • Поисковых запросов: {SearchQuery.objects.count()}

    ФОРМАТ ДАННЫХ:
    • Все данные в формате JSON
    • Кодировка: UTF-8
    • Версия формата: 1.0

    ПРИМЕЧАНИЕ:
    Это немедленный бэкап, созданный через админ-панель.
    Для восстановления используйте импорт через админку.
    """
                zipf.writestr('readme.txt', report)

            memory_file.seek(0)

            # Возвращаем файл
            response = HttpResponse(memory_file, content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Content-Length'] = len(memory_file.getvalue())

            # Логируем
            from .models import ActionLog
            ActionLog.objects.create(
                user=request.user,
                action_type='backup_download_immediate',
                description=f'Создан и скачан немедленный бэкап: {filename}',
                ip_address=request.META.get('REMOTE_ADDR'),
                browser=request.META.get('HTTP_USER_AGENT', '')[:255],
                action_data=metadata
            )

            return response

        except Exception as e:
            self.message_user(request, f'❌ Ошибка создания бэкапа: {str(e)}', level='error')
            return redirect('admin:wiki_backup_changelist')

admin.site.unregister(Group)
admin.site.register(Group, CustomGroupAdmin)