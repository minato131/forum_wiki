from .views import user_management, FAQView, HelpView, banned_page
from django.contrib.auth import views as auth_views
from .views import register
from django.contrib.auth import views as auth_views
from accounts.forms import CustomAuthenticationForm
from django.urls import path
from . import views
from django.contrib.admin.views.decorators import staff_member_required
from . import moderation_views
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
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
    path('article/<slug:slug>/resubmit/', views.article_resubmit, name='article_resubmit'),
    path('article/<slug:slug>/delete-by-author/', views.article_delete_by_author, name='article_delete_by_author'),

    # Модерация
    path('moderation/', views.moderation_queue, name='moderation_queue'),
    path('my-articles/', views.my_articles, name='my_articles'),
    path('article/<slug:slug>/send-to-editor/', views.send_to_editor, name='send_to_editor'),

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
    path('accounts/profile/', views.profile, name='profile'),

    # Отладка
    path('debug/test-like/', views.debug_test_like, name='debug_test_like'),
    path('debug/article-like/<slug:slug>/', views.debug_article_like, name='debug_article_like'),

    # Утилиты
    path('clean-latex/', views.clean_all_articles_latex, name='clean_latex'),
    path('editor/dashboard/', views.editor_dashboard, name='editor_dashboard'),
    path('comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),

    # Управление пользователями
    path('user-management/', views.user_management, name='user_management'),
    #Помощь
    path('help/', HelpView.as_view(), name='help'),
    path('help/faq/', FAQView.as_view(), name='faq'),

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
        template_name='registration/login.html',
        authentication_form=CustomAuthenticationForm,# ИЗМЕНИТЬ путь
        redirect_authenticated_user=True
    ), name='login'),

    path('logout/', auth_views.LogoutView.as_view(next_page='wiki:home'), name='logout'),
    path('register/', register, name='register'),

    # Восстановление пароля
    path('password-reset/', views.password_reset_request, name='password_reset_request'),
    path('password-reset/verify/', views.password_reset_verify, name='password_reset_verify'),
    path('password-reset/complete/', views.password_reset_complete, name='password_reset_complete'),

    # Telegram Auth
    path('auth/telegram/', views.telegram_auth, name='telegram_auth'),
    path('auth/telegram/callback/', views.telegram_callback, name='telegram_callback'),
    path('auth/telegram/disconnect/', views.telegram_disconnect, name='telegram_disconnect'),
    path('auth/telegram/code/', views.telegram_auth_code, name='telegram_auth_code'),
    path('auth/telegram/generate-code/', views.telegram_generate_test_code, name='telegram_generate_test_code'),
    path('auth/telegram/link/', views.telegram_link_with_code, name='telegram_link_with_code'),
    # Telegram Web App Auth
    path('auth/telegram/webapp/', views.telegram_webapp_login, name='telegram_webapp_login'),
    path('auth/telegram/webapp/callback/', views.telegram_webapp_callback, name='telegram_webapp_callback'),
    path('auth/telegram/quick/', views.telegram_quick_login, name='telegram_quick_login'),


    path('admin/group-permissions/', views.group_permissions_info, name='group_permissions_info'),
    path('article/<slug:slug>/resubmit/', views.article_resubmit, name='article_resubmit'),
    path('article/<slug:slug>/delete-by-author/', views.article_delete_by_author, name='article_delete_by_author'),
    path('article/<slug:slug>/return-to-draft/', views.article_return_to_draft, name='article_return_to_draft'),
    path('admin/action-logs/', views.action_logs_view, name='action_logs'),
    path('admin/action-logs/export-json/', views.export_logs_json, name='export_logs_json'),
    path('debug/create-log/', views.debug_create_log, name='debug_create_log'),
    path('debug/test-logs/', views.debug_test_logs, name='debug_test_logs'),
    path('tutorial/mark-seen/<str:tutorial_type>/', views.mark_tutorial_seen, name='mark_tutorial_seen'),
    path('tutorial/disable/', views.disable_tutorials, name='disable_tutorials'),
    path('tutorial/reset/', views.reset_tutorials, name='reset_tutorials'),

    path('article/<slug:slug>/export-pdf/', views.export_article_pdf, name='export_article_pdf'),
    path('articles/export/', views.export_articles_list, name='export_articles_list'),
    path('help/', HelpView.as_view(), name='help'),
    path('help/faq/', FAQView.as_view(), name='faq'),

    path('statistics/', views.StatisticsView.as_view(), name='statistics'),
    path('statistics/export/', views.ExportStatsView.as_view(), name='export_statistics'),
    path('api/update_stats/', views.update_stats_api, name='update_stats_api'),
    path('articles/', views.article_list, name='article_list'),
    path('statistics/export/pdf/', views.export_statistics_pdf, name='export_statistics_pdf'),
    path('statistics/export/json/', views.export_statistics_json, name='export_statistics_json'),
    path('comment/<int:comment_id>/like/', views.comment_like, name='comment_like'),
    # ... существующие URL ...
    path('profile/', views.profile, name='profile'),
    path('statistics/', views.user_statistics, name='statistics'),
    path('statistics/<str:username>/', views.user_statistics, name='user_statistics'),
    path('censorship-dashboard/', staff_member_required(views.censorship_dashboard), name='censorship_dashboard'),
    path('my-censorship-warnings/', views.my_censorship_warnings, name='my_censorship_warnings'),
    path('admin/user-warnings/', staff_member_required(views.user_warnings_list), name='user_warnings_list'),
    path('admin/reset-warnings/<int:user_id>/', staff_member_required(views.reset_user_warnings),
         name='reset_warnings'),
    path('moderation/dashboard/', moderation_views.moderation_dashboard, name='moderation_dashboard'),
    path('moderation/search/', moderation_views.user_search, name='user_search'),
    path('moderation/warned/', moderation_views.warned_users_list, name='warned_users_list'),
    path('moderation/banned/', moderation_views.banned_users_list, name='banned_users_list'),
    path('moderation/logs/', moderation_views.moderation_logs, name='moderation_logs'),
    path('moderation/user/<int:user_id>/', moderation_views.user_detail, name='user_detail'),
    path('moderation/warn/<int:user_id>/', moderation_views.warn_user, name='warn_user'),
    path('moderation/ban/<int:user_id>/', moderation_views.ban_user, name='ban_user'),
    path('moderation/unban/<int:user_id>/', moderation_views.unban_user, name='unban_user'),
    path('banned/', banned_page, name='banned'),
]