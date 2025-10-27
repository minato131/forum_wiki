from django.urls import path
from . import views
from .views import user_management
from django.contrib.auth import views as auth_views
from .views import register

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
    path('article/<slug:slug>/moderate/enhanced/', views.article_moderate_enhanced, name='article_moderate_enhanced'),
    path('article/<slug:slug>/like/', views.toggle_article_like, name='toggle_article_like'),
    path('article/<slug:slug>/delete/', views.article_delete, name='article_delete'),

    # Модерация
    path('moderation/', views.moderation_queue, name='moderation_queue'),
    path('my-articles/', views.my_articles, name='my_articles'),

    # Модерация комментариев
    path('article/<slug:slug>/add-moderation-comment/', views.add_moderation_comment, name='add_moderation_comment'),
    path('moderation-comment/<int:comment_id>/resolve/', views.resolve_moderation_comment, name='resolve_moderation_comment'),
    path('moderation-comment/<int:comment_id>/delete/', views.delete_moderation_comment, name='delete_moderation_comment'),

    # Редактура и ревью
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

    # Отладка
    path('debug/test-like/', views.debug_test_like, name='debug_test_like'),
    path('debug/article-like/<slug:slug>/', views.debug_article_like, name='debug_article_like'),

    # Утилиты
    path('clean-latex/', views.clean_all_articles_latex, name='clean_latex'),
    path('editor/dashboard/', views.editor_dashboard, name='editor_dashboard'),
    path('comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),

    # Управление пользователями
    path('user-management/', views.user_management, name='user_management'),

    # Сообщения
    path('messages/', views.messages_list, name='messages_list'),
    path('messages/<str:folder>/', views.messages_list, name='messages_list'),
    path('message/create/', views.message_create, name='message_create'),
    path('message/create/<int:recipient_id>/', views.message_create, name='message_create'),
    path('message/<int:message_id>/', views.message_detail, name='message_detail'),
    path('message/<int:message_id>/delete/', views.message_delete, name='message_delete'),
    path('message/send-quick/<int:user_id>/', views.send_quick_message, name='send_quick_message'),
    path('messages/unread-count/', views.get_unread_count, name='get_unread_count'),
    # Аутентификация
    path('login/', auth_views.LoginView.as_view(
        template_name='registration/login.html',  # ИЗМЕНИТЬ путь
        redirect_authenticated_user=True
    ), name='login'),
    path('login/', auth_views.LoginView.as_view(
        template_name='registration/login.html',  # ИЗМЕНИТЬ путь
        redirect_authenticated_user=True
    ), name='login'),

    path('logout/', auth_views.LogoutView.as_view(next_page='wiki:home'), name='logout'),
    path('register/', register, name='register'),
]