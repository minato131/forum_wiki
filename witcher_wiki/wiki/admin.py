from django.shortcuts import redirect
from rest_framework.generics import get_object_or_404

from .models import Article, Category, Comment, UserProfile, ArticleMedia, ModerationComment, ArticleRevision, BackupLog
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
from .models import CommentLike
import os
from .models import UserBan, UserWarning, ModerationLog

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


@admin.register(UserBan)
class UserBanAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'banned_by', 'created_at', 'expires_at', 'is_active']
    list_filter = ['is_active', 'duration', 'created_at']
    search_fields = ['user__username', 'reason', 'notes']
    readonly_fields = ['created_at', 'expires_at']
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'banned_by', 'reason')
        }),
        ('Параметры бана', {
            'fields': ('duration', 'expires_at', 'notes')
        }),
        ('Статус', {
            'fields': ('is_active', 'created_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.banned_by:
            obj.banned_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(UserWarning)
class UserWarningAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'issued_by', 'severity', 'created_at', 'is_active']
    list_filter = ['severity', 'is_active', 'created_at']
    search_fields = ['user__username', 'reason', 'related_content']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'issued_by', 'severity')
        }),
        ('Детали', {
            'fields': ('reason', 'related_content')
        }),
        ('Статус', {
            'fields': ('is_active', 'created_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.issued_by:
            obj.issued_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'moderator', 'target_user', 'action_type', 'created_at']
    list_filter = ['action_type', 'created_at']
    search_fields = ['moderator__username', 'target_user__username', 'details']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

@admin.register(ArticleRevision)
class ArticleRevisionAdmin(admin.ModelAdmin):
    list_display = ['article', 'author', 'created_at', 'comment']
    list_filter = ['created_at', 'author']
    search_fields = ['article__title', 'comment']
    readonly_fields = ['created_at']


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['article', 'author', 'created_at', 'is_deleted', 'get_like_count_display']
    list_filter = ['is_deleted', 'created_at']
    search_fields = ['content', 'article__title', 'author__username']
    readonly_fields = ['created_at', 'updated_at', 'like_count', 'author']
    actions = ['delete_comments', 'restore_comments']

    fieldsets = (
        ('Основная информация', {
            'fields': ('article', 'author', 'parent', 'content')
        }),
        ('Статистика', {
            'fields': ('like_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Модерация', {
            'fields': ('is_deleted',),
            'classes': ('collapse',)
        }),
    )

    def get_like_count_display(self, obj):
        return obj.like_count

    get_like_count_display.short_description = 'Лайки'

    def delete_comments(self, request, queryset):
        queryset.update(is_deleted=True)

    delete_comments.short_description = "Пометить как удаленные"

    def restore_comments(self, request, queryset):
        queryset.update(is_deleted=False)

    restore_comments.short_description = "Восстановить комментарии"


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


@admin.register(BackupLog)
class BackupLogAdmin(admin.ModelAdmin):
    """Админ-панель для логов бэкапов"""
    list_display = ['created_at', 'log_type_display', 'user', 'backup', 'message_short', 'ip_address']
    list_filter = ['log_type', 'created_at', 'user']
    search_fields = ['message', 'user__username', 'backup__name']
    readonly_fields = ['created_at', 'details_prettified']

    def log_type_display(self, obj):
        colors = {
            'created': 'green',
            'restored': 'blue',
            'deleted': 'red',
            'download': 'orange',
            'error': 'darkred'
        }
        color = colors.get(obj.log_type, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_log_type_display()
        )

    log_type_display.short_description = 'Тип'

    def message_short(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message

    message_short.short_description = 'Сообщение'

    def details_prettified(self, obj):
        if obj.details:
            return format_html(
                '<pre style="background: #f5f5f5; padding: 10px; border-radius: 5px; overflow-x: auto;">{}</pre>',
                json.dumps(obj.details, ensure_ascii=False, indent=2)
            )
        return '-'

    details_prettified.short_description = 'Детали'


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
            path('restore/', staff_member_required(self.restore_backup_view), name='wiki_backup_restore'),
            path('history/', staff_member_required(self.get_backup_history_view), name='wiki_backup_history'),
            path('<int:backup_id>/details/', staff_member_required(self.backup_details_view),
                 name='wiki_backup_details'),
            path('<int:backup_id>/delete/', staff_member_required(self.delete_backup_view), name='wiki_backup_delete'),
        ]
        return custom_urls + urls

    def backup_details_view(self, request, backup_id):
        """Получение деталей бэкапа для AJAX"""
        from django.http import JsonResponse
        from django.shortcuts import get_object_or_404

        backup = get_object_or_404(Backup, id=backup_id)

        status_info = self.get_backup_status_info(backup)

        details = {
            'id': backup.id,
            'name': backup.name,
            'created_at': backup.created_at.strftime('%d.%m.%Y %H:%M:%S'),
            'type': backup.backup_type,
            'status': backup.status,
            'status_display': status_info['display'],
            'status_color': status_info['color'],
            'size': backup.file_size_display(),
            'tables': backup.metadata.get('tables_count', 0) if backup.metadata else 0,
            'records': backup.metadata.get('total_records', 0) if backup.metadata else 0,
            'description': backup.metadata.get('description', '') if backup.metadata else '',
            'created_by': backup.metadata.get('created_by', '') if backup.metadata else '',
            'has_file': os.path.exists(os.path.join(settings.BASE_DIR, backup.file_path)) if backup.file_path else False
        }

        return JsonResponse({
            'success': True,
            'details': details
        })

    def create_backup_view(self, request):
        """Создание бэкапа через админку"""
        from django.shortcuts import render
        from datetime import date, timedelta
        import sqlite3
        import json
        import zipfile
        import tempfile
        import os
        from django.http import HttpResponse
        from django.utils import timezone
        from io import BytesIO
        from pathlib import Path
        from django.db import connections

        if request.method == 'POST':
            backup_type = request.POST.get('backup_type', 'full')
            start_date = request.POST.get('start_date', '')
            end_date = request.POST.get('end_date', '')
            description = request.POST.get('description', '')

            try:
                # ПОПРАВЛЕНО: Получаем путь к базе данных из настроек Django
                from django.conf import settings
                import sqlite3

                # Получаем информацию о подключении к базе данных
                db_settings = settings.DATABASES['default']

                if db_settings['ENGINE'] == 'django.db.backends.sqlite3':
                    # Для SQLite
                    db_name = db_settings['NAME']
                    # Если путь относительный, делаем его абсолютным относительно BASE_DIR
                    if not os.path.isabs(db_name):
                        db_path = os.path.join(settings.BASE_DIR, db_name)
                    else:
                        db_path = db_name
                else:
                    # Для других баз данных (PostgreSQL, MySQL) экспортируем через dumpdata
                    return self.create_backup_for_other_databases(request, backup_type, start_date, end_date,
                                                                  description)

                # Проверяем существование файла
                if not os.path.exists(db_path):
                    # Создаем абсолютный путь
                    db_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')
                    if not os.path.exists(db_path):
                        # Пробуем найти в других возможных местах
                        possible_paths = [
                            os.path.join(settings.BASE_DIR, 'db.sqlite3'),
                            os.path.join(settings.BASE_DIR, 'database', 'db.sqlite3'),
                            os.path.join(settings.BASE_DIR, 'data', 'db.sqlite3'),
                            'db.sqlite3',
                        ]

                        for possible_path in possible_paths:
                            if os.path.exists(possible_path):
                                db_path = possible_path
                                break
                        else:
                            # Если файл не найден, показываем диагностическую информацию
                            error_msg = f'''
                            ❌ Файл базы данных не найден!<br><br>
                            Проверенные пути:<br>
                            - {os.path.join(settings.BASE_DIR, 'db.sqlite3')}<br>
                            - {os.path.join(settings.BASE_DIR, 'database', 'db.sqlite3')}<br>
                            - {os.path.join(settings.BASE_DIR, 'data', 'db.sqlite3')}<br>
                            - db.sqlite3<br><br>
                            Текущий BASE_DIR: {settings.BASE_DIR}<br>
                            Настройки DATABASES: {db_settings['NAME']}
                            '''
                            self.message_user(request, format_html(error_msg), level='error')
                            return redirect('admin:wiki_backup_create')

                self.message_user(request, f'✅ Найден файл базы данных: {db_path}', level='info')

                # Создаем соединение с базой данных
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Получаем список всех таблиц
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
                tables = [row[0] for row in cursor.fetchall()]

                self.message_user(request, f'✅ Найдено таблиц: {len(tables)}', level='info')

                # Создаем структуру бэкапа
                backup_data = {
                    'metadata': {
                        'created_at': timezone.now().isoformat(),
                        'backup_type': backup_type,
                        'start_date': start_date if start_date else None,
                        'end_date': end_date if end_date else None,
                        'description': description,
                        'tables_count': len(tables),
                        'database': 'sqlite3',
                        'version': '1.0',
                        'db_path': db_path,
                        'total_records': 0
                    },
                    'tables': {}
                }

                # Фильтрация по дате если указаны даты
                date_filter = None
                if start_date or end_date:
                    date_filter = {
                        'start': start_date if start_date else None,
                        'end': end_date if end_date else None
                    }

                # Для каждой таблицы получаем данные
                total_records = 0
                for table_name in tables:
                    if table_name.startswith('sqlite_'):
                        continue

                    # Получаем структуру таблицы
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns_info = cursor.fetchall()
                    columns = [col[1] for col in columns_info]

                    # Строим запрос с учетом фильтрации по дате
                    query = f"SELECT * FROM {table_name}"
                    params = []

                    if date_filter and date_filter['start'] and date_filter['end']:
                        # Проверяем, есть ли в таблице поле created_at или date
                        column_names = [col[1] for col in columns_info]
                        date_column = None

                        if 'created_at' in column_names:
                            date_column = 'created_at'
                        elif 'date' in column_names:
                            date_column = 'date'
                        elif 'updated_at' in column_names:
                            date_column = 'updated_at'

                        if date_column:
                            query += f" WHERE {date_column} >= ? AND {date_column} <= ?"
                            params.extend([date_filter['start'], date_filter['end']])

                    cursor.execute(query, params)
                    rows = cursor.fetchall()

                    # Конвертируем строки в словари
                    table_data = []
                    for row in rows:
                        row_dict = {}
                        for idx, col_name in enumerate(columns):
                            value = row[idx]
                            # Конвертируем datetime объекты в строки
                            if isinstance(value, (bytes, bytearray)):
                                value = value.decode('utf-8', errors='ignore')
                            row_dict[col_name] = value
                        table_data.append(row_dict)

                    table_record_count = len(table_data)
                    total_records += table_record_count

                    backup_data['tables'][table_name] = {
                        'columns': columns,
                        'count': table_record_count,
                        'data': table_data
                    }

                    self.message_user(request, f'✅ Таблица "{table_name}": {table_record_count} записей', level='info')

                backup_data['metadata']['total_records'] = total_records
                conn.close()

                # Создаем имя файла
                timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                filename = f'witcher_wiki_backup_{backup_type}_{timestamp}'
                backup_filename = f'{filename}.zip'

                # Создаем ZIP архив
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    # Добавляем основной JSON файл с данными
                    json_data = json.dumps(backup_data, ensure_ascii=False, indent=2, default=str)
                    zip_file.writestr(f'backup_data.json', json_data)

                    # Добавляем README файл
                    readme_content = f"""Резервная копия Witcher Wiki
    ================================

    Дата создания: {timezone.now().strftime('%d.%m.%Y %H:%M:%S')}
    Тип бэкапа: {backup_type}
    Описание: {description or 'Нет описания'}

    Период данных:
    - Начало: {start_date if start_date else 'Все данные'}
    - Конец: {end_date if end_date else 'Все данные'}

    Статистика:
    - Таблиц: {len(backup_data['tables'])}
    - Всего записей: {total_records}
    - Общий объем данных: {len(json_data)} байт

    Для восстановления:
    1. Распакуйте этот архив
    2. Используйте файл backup_data.json для восстановления через админ-панель
    3. Или импортируйте данные через manage.py команды

    Создано автоматически системой Witcher Wiki
    """
                    zip_file.writestr('README.txt', readme_content)

                zip_buffer.seek(0)
                zip_data = zip_buffer.read()

                # ============ ИСПРАВЛЕНО: СОХРАНЕНИЕ БЭКАПА В БАЗУ ДАННЫХ ============
                from .models import Backup, ActionLog
                import uuid

                # Создаем путь для сохранения файла
                backups_dir = os.path.join(settings.BASE_DIR, 'backups')
                os.makedirs(backups_dir, exist_ok=True)

                backup_file_path = os.path.join(backups_dir, backup_filename)

                # Сохраняем файл на диск
                with open(backup_file_path, 'wb') as f:
                    f.write(zip_data)

                # Создаем относительный путь для хранения в БД
                relative_path = os.path.join('backups', backup_filename)

                # Создаем запись в базе данных
                backup = Backup.objects.create(
                    name=filename,
                    backup_type=backup_type,
                    file_path=relative_path,
                    file_size=len(zip_data),
                    status='completed',
                    metadata={
                        'description': description,
                        'start_date': start_date if start_date else None,
                        'end_date': end_date if end_date else None,
                        'tables_count': len(backup_data['tables']),
                        'total_records': total_records,
                        'created_by': request.user.username if request.user else 'system',
                        'filename': backup_filename,
                        'database_size': os.path.getsize(db_path) if os.path.exists(db_path) else 0,
                        'backup_format': 'json_zip'
                    }
                )

                # ============ СОЗДАЕМ ЛОГ ДЕЙСТВИЯ ============
                # Используем ActionLogger для согласованного логирования
                from .logging_utils import ActionLogger

                ActionLogger.log_action(
                    request=request,
                    action_type='backup_created',
                    description=f'Создана резервная копия "{filename}" ({backup_type})',
                    target_object=backup,
                    extra_data={
                        'backup_id': backup.id,
                        'backup_name': filename,
                        'backup_type': backup_type,
                        'file_size': len(zip_data),
                        'tables_count': len(backup_data['tables']),
                        'records_count': total_records,
                        'description': description,
                        'file_path': relative_path,
                        'status': 'completed',
                        'created_by': request.user.username if request.user else 'system'
                    }
                )

                # Также создаем BackupLog для истории бэкапов
                BackupLog.objects.create(
                    backup=backup,
                    log_type='created',
                    user=request.user,
                    message=f'Резервная копия "{filename}" успешно создана',
                    details={
                        'name': backup.name,
                        'type': backup.backup_type,
                        'size': backup.file_size_display(),
                        'path': backup.file_path,
                        'created_by': request.user.username,
                        'records_count': total_records,
                        'tables_count': len(backup_data['tables']),
                    }
                )

                # Отправляем файл для скачивания
                response = HttpResponse(
                    zip_data,
                    content_type='application/zip'
                )
                response['Content-Disposition'] = f'attachment; filename="{backup_filename}"'

                # Добавляем сообщения об успешном создании
                success_message = f'''
                ✅ <strong>Бэкап успешно создан!</strong><br>
                • Файл: {backup_filename}<br>
                • Размер: {self.format_size(len(zip_data))}<br>
                • Таблиц: {len(backup_data["tables"])}<br>
                • Записей: {total_records}<br>
                • ID в базе: {backup.id}<br>
                • Сохранен в: {relative_path}
                '''

                self.message_user(request, format_html(success_message), level='success')

                return response

            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                print(f"Ошибка создания бэкапа: {str(e)}")
                print(f"Детали ошибки:\n{error_details}")

                # Создаем лог ошибки
                from .models import ActionLog

                ActionLog.objects.create(
                    user=request.user,
                    action_type='error',
                    description=f'Ошибка создания бэкапа: {str(e)[:200]}',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    browser=request.META.get('HTTP_USER_AGENT', '')[:255],
                    operating_system='Unknown',
                    action_data={
                        'error': str(e),
                        'backup_type': backup_type,
                        'description': description
                    }
                )

                error_msg = f'''
                ❌ <strong>Ошибка при создании бэкапа!</strong><br><br>
                <strong>Ошибка:</strong> {str(e)}<br><br>
                <strong>Детали:</strong><br>
                <pre style="background: #f5f5f5; padding: 10px; border-radius: 5px; max-height: 300px; overflow: auto;">
                {error_details}
                </pre>
                '''
                self.message_user(request, format_html(error_msg), level='error')
                return redirect('admin:wiki_backup_create')

        # GET запрос - показываем форму
        today = date.today()
        dates_list = []
        for i in range(30):
            current_date = today - timedelta(days=i)
            dates_list.append(current_date)

        context = {
            'title': 'Создание резервной копии',
            'dates_list': dates_list,
            'today': today,
        }
        return render(request, 'admin/wiki/backup/create_backup.html', context)

    def format_size(self, size_bytes):
        """Форматирование размера файла"""
        import math
        if size_bytes == 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"

    def create_backup_for_other_databases(self, request, backup_type, start_date, end_date, description):
        """Создание бэкапа для PostgreSQL, MySQL и других баз данных"""
        from django.core.management import call_command
        from io import StringIO
        import json
        import zipfile
        from django.http import HttpResponse
        from io import BytesIO
        from django.utils import timezone

        try:
            # Используем Django dumpdata для экспорта
            output = StringIO()
            call_command('dumpdata', format='json', indent=2, stdout=output)
            data = json.loads(output.getvalue())

            # Фильтрация по дате (если нужно)
            if start_date or end_date:
                filtered_data = []
                for item in data:
                    # Проверяем поля с датами
                    model = item['model']
                    fields = item['fields']

                    # Определяем поле с датой
                    date_field = None
                    if 'created_at' in fields:
                        date_field = 'created_at'
                    elif 'date' in fields:
                        date_field = 'date'
                    elif 'updated_at' in fields:
                        date_field = 'updated_at'

                    if date_field:
                        item_date = fields[date_field]
                        if isinstance(item_date, str):
                            item_date = item_date[:10]  # Берем только дату

                        # Фильтруем по дате
                        if start_date and item_date < start_date:
                            continue
                        if end_date and item_date > end_date:
                            continue

                    filtered_data.append(item)

                data = filtered_data

            # Создаем имя файла
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f'witcher_wiki_backup_{backup_type}_{timestamp}'

            # Создаем ZIP архив
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                json_data = json.dumps(data, ensure_ascii=False, indent=2, default=str)
                zip_file.writestr(f'backup_data.json', json_data)

                # Добавляем метаданные
                metadata = {
                    'created_at': timezone.now().isoformat(),
                    'backup_type': backup_type,
                    'start_date': start_date,
                    'end_date': end_date,
                    'description': description,
                    'format': 'json',
                    'version': '1.0',
                    'record_count': len(data)
                }
                zip_file.writestr('metadata.json', json.dumps(metadata, indent=2))

            zip_buffer.seek(0)

            # Отправляем файл
            response = HttpResponse(
                zip_buffer.read(),
                content_type='application/zip'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}.zip"'

            return response

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            error_msg = f'❌ Ошибка при создании бэкапа: {str(e)}\n\n{error_details}'
            self.message_user(request, error_msg, level='error')
            return redirect('admin:wiki_backup_create')

    def restore_backup_view(self, request):
        """Восстановление из бэкапа - загрузка файла"""
        from django.shortcuts import render
        import zipfile
        import json
        import sqlite3
        import tempfile
        import os
        from django.db import transaction
        from django.conf import settings
        import shutil

        if request.method == 'POST' and request.FILES.get('backup_file'):
            backup_file = request.FILES['backup_file']

            try:
                # Проверяем тип файла
                if not backup_file.name.endswith('.zip'):
                    self.message_user(request, '❌ Файл должен быть в формате ZIP', level='error')
                    return redirect('admin:wiki_backup_restore')

                # Читаем ZIP файл
                with zipfile.ZipFile(backup_file, 'r') as zip_file:
                    # Проверяем наличие необходимых файлов
                    if 'backup_data.json' not in zip_file.namelist():
                        self.message_user(request, '❌ В архиве отсутствует файл backup_data.json', level='error')
                        return redirect('admin:wiki_backup_restore')

                    # Извлекаем данные
                    json_data = zip_file.read('backup_data.json')
                    backup_data = json.loads(json_data.decode('utf-8'))

                    # Проверяем структуру бэкапа
                    if 'tables' not in backup_data or 'metadata' not in backup_data:
                        self.message_user(request, '❌ Неверный формат файла бэкапа', level='error')
                        return redirect('admin:wiki_backup_restore')

                # Получаем путь к текущей БД
                db_settings = settings.DATABASES['default']

                if db_settings['ENGINE'] != 'django.db.backends.sqlite3':
                    self.message_user(request, '❌ Восстановление поддерживается только для SQLite', level='error')
                    return redirect('admin:wiki_backup_restore')

                db_path = db_settings['NAME']
                if not os.path.isabs(db_path):
                    db_path = os.path.join(settings.BASE_DIR, db_path)

                # Создаем резервную копию текущей БД перед восстановлением
                timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                backup_dir = os.path.join(settings.BASE_DIR, 'backups', 'pre_restore')
                os.makedirs(backup_dir, exist_ok=True)
                backup_current_path = os.path.join(backup_dir, f'backup_pre_restore_{timestamp}.sqlite3')

                shutil.copy2(db_path, backup_current_path)

                # Восстанавливаем данные
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                try:
                    with transaction.atomic():
                        # Получаем список всех таблиц в текущей БД
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                        current_tables = [row[0] for row in cursor.fetchall()]

                        # Отключаем foreign keys
                        cursor.execute("PRAGMA foreign_keys = OFF")

                        # Очищаем таблицы в обратном порядке (чтобы избежать ошибок foreign keys)
                        for table in reversed(current_tables):
                            cursor.execute(f"DELETE FROM {table}")

                        # Восстанавливаем данные из бэкапа
                        restored_tables = 0
                        restored_records = 0

                        for table_name, table_info in backup_data.get('tables', {}).items():
                            columns = table_info.get('columns', [])
                            data = table_info.get('data', [])

                            if columns and data:
                                # Проверяем существование таблицы
                                cursor.execute(
                                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                                if not cursor.fetchone():
                                    # Таблица не существует, пропускаем
                                    continue

                                # Создаем placeholders для SQL запроса
                                placeholders = ', '.join(['?'] * len(columns))
                                column_names = ', '.join([f'"{col}"' for col in columns])

                                for row in data:
                                    values = []
                                    for col in columns:
                                        val = row.get(col)
                                        # Конвертируем None в NULL
                                        if val is None:
                                            values.append(None)
                                        else:
                                            values.append(str(val))

                                    cursor.execute(
                                        f"INSERT OR REPLACE INTO {table_name} ({column_names}) VALUES ({placeholders})",
                                        values
                                    )
                                    restored_records += 1

                                restored_tables += 1

                        # Включаем foreign keys обратно
                        cursor.execute("PRAGMA foreign_keys = ON")
                        conn.commit()

                    success_message = f'''
                    ✅ База данных успешно восстановлена!<br><br>
                    <strong>Статистика восстановления:</strong><br>
                    • Восстановлено таблиц: {restored_tables}<br>
                    • Восстановлено записей: {restored_records}<br>
                    • Файл бэкапа: {backup_file.name}<br><br>
                    <strong>Создана резервная копия перед восстановлением:</strong><br>
                    • {os.path.basename(backup_current_path)}<br>
                    • Путь: {backup_current_path}
                    '''

                    # Создаем запись о восстановлении
                    from .models import Backup
                    backup = Backup.objects.create(
                        name=f'RESTORE_{backup_file.name}_{timestamp}',
                        backup_type='restore',
                        file_path=backup_current_path,
                        file_size=os.path.getsize(backup_current_path),
                        status='completed',
                        metadata={
                            'restored_from': backup_file.name,
                            'restored_tables': restored_tables,
                            'restored_records': restored_records,
                            'original_metadata': backup_data['metadata']
                        }
                    )

                    # Логируем действие восстановления
                    from .logging_utils import ActionLogger
                    ActionLogger.log_action(
                        request=request,
                        action_type='backup_restored',
                        description=f'Восстановлен бэкап из файла: {backup_file.name}',
                        target_object=backup,
                        extra_data={
                            'backup_id': backup.id,
                            'backup_name': backup.name,
                            'restored_tables': restored_tables,
                            'restored_records': restored_records,
                            'original_file': backup_file.name,
                        }
                    )

                    self.message_user(request, format_html(success_message), level='success')

                except Exception as restore_error:
                    conn.rollback()
                    raise restore_error
                finally:
                    conn.close()

                return redirect('admin:wiki_backup_changelist')

            except zipfile.BadZipFile:
                self.message_user(request, '❌ Некорректный ZIP файл', level='error')
            except json.JSONDecodeError:
                self.message_user(request, '❌ Ошибка чтения JSON данных в архиве', level='error')
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                error_msg = f'''
                ❌ Ошибка при восстановлении!<br><br>
                <strong>Ошибка:</strong> {str(e)}<br><br>
                <strong>Детали:</strong><br>
                <pre style="background: #f5f5f5; padding: 10px; border-radius: 5px; max-height: 200px; overflow: auto; font-size: 12px;">
                {error_details}
                </pre>
                '''
                self.message_user(request, format_html(error_msg), level='error')

        # GET запрос - показываем форму загрузки
        context = {
            'title': 'Восстановление базы данных',
            'opts': self.model._meta,
        }
        return render(request, 'admin/wiki/backup/restore_backup.html', context)

    def get_client_ip(self, request):
        """Получение IP адреса клиента"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def get_os_info(self, request):
        """Получение информации об ОС"""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if 'Windows' in user_agent:
            return 'Windows'
        elif 'Mac' in user_agent:
            return 'Mac OS'
        elif 'Linux' in user_agent:
            return 'Linux'
        elif 'Android' in user_agent:
            return 'Android'
        elif 'iOS' in user_agent:
            return 'iOS'
        else:
            return 'Unknown'

    def get_backup_history_view(self, request):
        """Получение истории бэкапов для AJAX запроса - УПРОЩЕННЫЙ ВАРИАНТ"""
        from django.http import JsonResponse
        from .models import Backup
        from django.utils import timezone
        import os
        from django.conf import settings

        try:
            # Получаем последние 20 бэкапов
            backups = Backup.objects.all().order_by('-created_at')[:20]

            history_data = []
            for backup in backups:
                # Базовый статус
                status = backup.status
                status_display = "Завершен" if status == 'completed' else "Ошибка" if status == 'failed' else "В процессе"
                status_color = "#4CAF50" if status == 'completed' else "#f44336" if status == 'failed' else "#ff9800"

                # Метаданные
                metadata = {}
                if backup.metadata:
                    try:
                        metadata = backup.metadata
                    except:
                        metadata = {}

                # Проверяем файл
                has_file = False
                if backup.file_path:
                    try:
                        full_path = os.path.join(settings.BASE_DIR, backup.file_path.lstrip('/'))
                        has_file = os.path.exists(full_path)
                    except:
                        has_file = False

                history_data.append({
                    'id': backup.id,
                    'name': backup.name or f"Бэкап #{backup.id}",
                    'created_at': backup.created_at.strftime('%d.%m.%Y %H:%M:%S'),
                    'type': backup.backup_type or 'full',
                    'status': status,
                    'status_display': status_display,
                    'status_color': status_color,
                    'size': backup.file_size_display(),
                    'tables': metadata.get('tables_count', 0),
                    'models': metadata.get('models_count', 0),
                    'records': metadata.get('total_records', 0),
                    'description': metadata.get('description', ''),
                    'created_by': metadata.get('created_by', ''),
                    'has_file': has_file
                })

            return JsonResponse({
                'success': True,
                'history': history_data,
                'total': len(history_data),
                'timestamp': timezone.now().isoformat()
            })

        except Exception as e:
            print(f"Ошибка в get_backup_history_view: {str(e)}")  # Для отладки
            return JsonResponse({
                'success': False,
                'error': str(e),
                'history': []
            })

    def delete_backup_view(self, request, backup_id):
        """Удаление бэкапа"""
        from django.http import JsonResponse
        from django.shortcuts import get_object_or_404
        import os
        from django.conf import settings
        from .models import Backup, ActionLog
        from .logging_utils import ActionLogger

        backup = get_object_or_404(Backup, id=backup_id)

        try:
            # Логируем перед удалением
            ActionLogger.log_action(
                request=request,
                action_type='backup_deleted',
                description=f'Удален бэкап: {backup.name}',
                target_object=backup,
                extra_data={
                    'backup_id': backup.id,
                    'backup_name': backup.name,
                    'file_path': backup.file_path,
                    'file_size': backup.file_size,
                    'backup_type': backup.backup_type,
                }
            )

            # Удаляем файл если существует
            if backup.file_path:
                full_path = os.path.join(settings.BASE_DIR, backup.file_path)
                if os.path.exists(full_path):
                    os.remove(full_path)

            # Создаем BackupLog перед удалением
            BackupLog.objects.create(
                backup=None,  # Ссылка на бэкап будет потеряна после удаления
                log_type='deleted',
                user=request.user,
                message=f'Удален бэкап: {backup.name}',
                details={
                    'backup_id': backup.id,
                    'backup_name': backup.name,
                    'file_path': backup.file_path,
                    'file_size': backup.file_size,
                    'backup_type': backup.backup_type,
                    'created_at': backup.created_at.isoformat() if backup.created_at else None,
                }
            )

            # Удаляем запись из БД
            backup_name = backup.name
            backup.delete()

            return JsonResponse({
                'success': True,
                'message': f'Бэкап {backup_name} успешно удален'
            })

        except Exception as e:
            # Логируем ошибку
            ActionLogger.log_action(
                request=request,
                action_type='error',
                description=f'Ошибка удаления бэкапа: {backup.name}',
                extra_data={
                    'error': str(e),
                    'backup_id': backup.id,
                    'backup_name': backup.name,
                }
            )
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

    def get_backup_status_info(self, backup):
        """Информация о статусе бэкапа для отображения"""
        if backup.status == 'completed':
            return {
                'display': 'Завершен',
                'color': '#4CAF50',
                'icon': 'fa-check-circle'
            }
        elif backup.status == 'in_progress':
            return {
                'display': 'В процессе',
                'color': '#FF9800',
                'icon': 'fa-spinner fa-spin'
            }
        elif backup.status == 'failed':
            return {
                'display': 'Ошибка',
                'color': '#F44336',
                'icon': 'fa-exclamation-circle'
            }
        else:
            return {
                'display': 'Неизвестно',
                'color': '#9E9E9E',
                'icon': 'fa-question-circle'
            }

    def download_backup_view(self, request, backup_id):
        """Скачивание бэкапа"""
        from django.shortcuts import get_object_or_404
        from .logging_utils import ActionLogger

        backup = get_object_or_404(Backup, id=backup_id)

        if not os.path.exists(backup.file_path):
            self.message_user(request, '❌ Файл бэкапа не найден', level='error')
            return redirect('admin:wiki_backup_changelist')

        # Логируем скачивание
        ActionLogger.log_action(
            request=request,
            action_type='backup_downloaded',
            description=f'Скачан бэкап: {backup.name}',
            target_object=backup,
            extra_data={
                'backup_id': backup.id,
                'backup_name': backup.name,
                'file_size': backup.file_size,
                'file_path': backup.file_path,
            }
        )

        # Создаем BackupLog для истории скачивания
        BackupLog.objects.create(
            backup=backup,
            log_type='download',
            user=request.user,
            message=f'Скачан бэкап: {backup.name}',
            details={
                'backup_id': backup.id,
                'backup_name': backup.name,
                'file_size': backup.file_size,
                'file_path': backup.file_path,
                'downloaded_at': timezone.now().isoformat(),
            }
        )

        with open(backup.file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{backup.name}.zip"'
            return response

@admin.register(CommentLike)
class CommentLikeAdmin(admin.ModelAdmin):
    list_display = ['comment', 'user', 'created_at']
    list_filter = ['created_at', 'user']
    search_fields = ['comment__content', 'user__username']
    readonly_fields = ['created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
admin.site.unregister(Group)
admin.site.register(Group, CustomGroupAdmin)