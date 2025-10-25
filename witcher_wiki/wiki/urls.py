from django.urls import path
from . import views

app_name = 'wiki'

urlpatterns = [
    # Основные страницы
    path('', views.home, name='home'),
    path('search/', views.search, name='search'),

    # Категории
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),

    # Статьи
    path('article/create/', views.article_create, name='article_create'),
    path('article/<slug:slug>/', views.article_detail, name='article_detail'),
    path('article/<slug:slug>/edit/', views.article_edit, name='article_edit'),
    path('article/<slug:slug>/moderate/', views.article_moderate, name='article_moderate'),
    path('article/<slug:slug>/like/', views.toggle_article_like, name='toggle_article_like'),

    # Модерация
    path('moderation/', views.moderation_queue, name='moderation_queue'),
    path('my-articles/', views.my_articles, name='my_articles'),

    # Новые URL для расширенной модерации
    path('article/<slug:slug>/moderate/comment/', views.add_moderation_comment, name='add_moderation_comment'),
    path('article/<slug:slug>/editor-review/', views.editor_review, name='editor_review'),
    path('article/<slug:slug>/author-review/', views.author_review, name='author_review'),

    # Медиа
    path('media/<int:media_id>/delete/', views.delete_media, name='delete_media'),

    # Управление категориями
    path('categories/', views.category_management, name='category_management'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:category_id>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:category_id>/delete/', views.category_delete, name='category_delete'),
    path('categories/<int:category_id>/toggle-featured/', views.category_toggle_featured,
         name='category_toggle_featured'),
    path('categories/json/', views.get_categories_json, name='categories_json'),

    # Пользовательские профили
    path('user/<str:username>/', views.user_public_profile, name='user_public_profile'),
    path('liked-articles/', views.liked_articles, name='liked_articles'),

    path('debug/test-like/', views.debug_test_like, name='debug_test_like'),
    path('debug/article-like/<slug:slug>/', views.debug_article_like, name='debug_article_like'),

    path('clean-latex/', views.clean_all_articles_latex, name='clean_latex'),
    path('editor/dashboard/', views.editor_dashboard, name='editor_dashboard'),
    path('comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),
]