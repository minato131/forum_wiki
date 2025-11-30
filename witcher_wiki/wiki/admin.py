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

admin.site.unregister(Group)
admin.site.register(Group, CustomGroupAdmin)