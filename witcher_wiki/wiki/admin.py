# admin.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
from django.contrib import admin
from django.contrib.auth.models import Group
from .models import Article, Category, Comment, UserProfile, ArticleMedia, ModerationComment, ArticleRevision

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

# Создаем категорию "Магия"
magic_category, created = Category.objects.get_or_create(
    name='Магия',
    defaults={
        'slug': 'magic',
        'description': 'Статьи о магии, заклинаниях, знаках и магических существах',
        'is_featured': True,
        'display_order': 4,
        'icon': '🔮'
    }
)

# Создаем категорию "События"
events_category, created = Category.objects.get_or_create(
    name='События',
    defaults={
        'slug': 'events',
        'description': 'Важные события, битвы, исторические моменты вселенной Ведьмака',
        'is_featured': True,
        'display_order': 5,
        'icon': '📜'
    }
)

print("Категории созданы!")