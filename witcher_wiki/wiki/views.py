from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Sum, Avg
from django.core.paginator import Paginator
from django.utils.text import slugify
import os
import re
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
import json
from django.utils import timezone
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import user_passes_test
from .models import Article, Category, Comment,SearchHistory,CommentLike, ArticleMedia, UserProfile, ArticleLike, ModerationComment, SearchQuery, \
    Message, EmailVerification
from .forms import ArticleForm, CommentForm, SearchForm, CategoryForm, ProfileUpdateForm, MessageForm, QuickMessageForm, \
    CustomUserCreationForm, CodeVerificationForm, PasswordResetRequestForm, EmailVerificationForm, PasswordResetForm, \
    CompleteRegistrationForm
from django.urls import reverse
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.contrib.auth import login
from django.contrib import messages
from django.conf import settings
from .models import TelegramUser, UserProfile
import json
from .telegram_auth_manager import TelegramAuthManager
from .telegram_bot_sync import sync_bot
from .telegram_utils import TelegramAuth
from django.contrib.auth import login as auth_login
from .permissions import GROUP_PERMISSIONS
from .permissions import user_can_moderate, user_can_edit_content
from .logging_utils import log_article_creation, log_article_moderation, log_user_login, log_user_logout
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from .models import ActionLog
from .logging_utils import ActionLogger
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import io
from django.utils.text import Truncator
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from .models import Article
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io
from .models import HelpSection, FAQ
from django.views.generic import View, TemplateView, ListView, DetailView
from django.views import View
from django.shortcuts import render
from .utils.stats_collector import StatsCollector
from django.views.generic import TemplateView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.decorators.csrf import csrf_exempt
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import mm, inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
import os
from django.conf import settings
from .backup_utils import create_backup, cleanup_old_backups, create_backup_for_period
from .models import Backup
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.contrib import messages
from .models import Backup, BackupLog
import threading
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib import messages
from django.conf import settings
from .censorship_utils import check_request_for_banned_words, add_censorship_warning
from django.contrib.admin.views.decorators import staff_member_required
from .censorship import CensorshipService
from .censorship_warnings import CensorshipWarningSystem
from .moderation_views import (
    moderation_dashboard,
    user_search,
    user_detail,
    banned_users_list,
    warned_users_list,
    moderation_logs,
    clear_old_logs,
)
# from wiki.middleware import CensorshipMiddleware
from .models import UserWarning
from .models import UserBan

def clean_latex_from_content(content):
    """
    Удаляет LaTeX-команды из контента
    """
    if not content:
        return content

    # Удаляем простые LaTeX-команды вида \command{content}
    content = re.sub(r'\\[a-zA-Z]+\{.*?\}', '', content)

    # Удаляем математические окружения \[ \]
    content = re.sub(r'\\\[.*?\\\]', '', content, flags=re.DOTALL)

    # Удаляем математические окружения $$ $$
    content = re.sub(r'\$\$.*?\$\$', '', content, flags=re.DOTALL)

    # Удаляем одиночные $ для inline math
    content = re.sub(r'\$[^$]*?\$', '', content)

    return content.strip()


def home(request):
    # Основные категории для горизонтального скролла
    featured_categories = Category.objects.filter(
        is_featured=True
    ).annotate(
        article_count=Count('articles')
    ).order_by('display_order', 'name')[:10]

    # Последние опубликованные статьи
    recent_articles = Article.objects.filter(status='published').order_by('-created_at')[:6]

    # Популярные категории (по количеству статей)
    popular_categories = Category.objects.annotate(
        article_count=Count('articles')
    ).order_by('-article_count')[:8]

    # Все категории для навигации
    categories = Category.objects.all()

    context = {
        'featured_categories': featured_categories,
        'recent_articles': recent_articles,
        'popular_categories': popular_categories,
        'categories': categories,
    }
    return render(request, 'wiki/home.html', context)


@login_required
def toggle_comment_like(request, comment_id):
    """Добавляет/убирает лайк комментария"""
    comment = get_object_or_404(Comment, id=comment_id)

    if request.method == 'POST':
        try:
            was_liked = comment.is_liked_by_user(request.user)

            # Переключаем лайк
            liked = comment.toggle_like(request.user)
            likes_count = comment.get_likes_count()

            action = 'comment_like_add' if liked else 'comment_like_remove'
            description = f'Пользователь {request.user.username} {"поставил" if liked else "убрал"} лайк комментарию'

            ActionLogger.log_action(
                request=request,
                action_type=action,
                description=description,
                target_object=comment,
                extra_data={
                    'comment_id': comment.id,
                    'article_title': comment.article.title,
                    'was_liked': was_liked,
                    'now_liked': liked,
                    'total_likes': likes_count,
                }
            )

            return JsonResponse({
                'success': True,
                'liked': liked,
                'likes_count': likes_count,
                'was_liked': was_liked,
                'status_changed': was_liked != liked
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid method'})

def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    articles_list = Article.objects.filter(categories=category, status='published').order_by('-created_at')

    # Пагинация
    paginator = Paginator(articles_list, 12)
    page_number = request.GET.get('page')
    articles = paginator.get_page(page_number)

    context = {
        'category': category,
        'articles': articles,
        'articles_list': articles_list,
    }
    return render(request, 'wiki/category_detail.html', context)


# views.py - ОБНОВИТЬ функцию search

def search(request):
    query = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '')
    tag_filter = request.GET.get('tag', '')
    author_filter = request.GET.get('author', '')
    status_filter = request.GET.get('status', '')
    sort_by = request.GET.get('sort', 'relevance')
    time_filter = request.GET.get('time', 'all')
    min_views = request.GET.get('min_views', '')
    min_likes = request.GET.get('min_likes', '')
    has_media = request.GET.get('has_media', '')
    article_length = request.GET.get('length', '')

    results = []
    total_count = 0
    filters_applied = []

    if query or tag_filter or category_filter or any([author_filter, status_filter, min_views, min_likes, has_media]):
        # Сохраняем поисковый запрос в SearchQuery
        if query:
            try:
                search_query_obj, created = SearchQuery.objects.get_or_create(query=query)
                if not created:
                    search_query_obj.count += 1
                    search_query_obj.save()
            except Exception as e:
                print(f"Ошибка при сохранении поискового запроса: {e}")

        # Сохраняем историю поиска
        if query:
            SearchHistory.objects.create(
                query=query,
                user=request.user if request.user.is_authenticated else None,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )

        # Улучшенный поиск с приоритетом
        search_query = Q()

        if query:
            # Разделяем поиск на совпадения в названии и контенте
            search_query = (Q(title__icontains=query) |
                            Q(content__icontains=query) |
                            Q(excerpt__icontains=query) |
                            Q(tags__name__icontains=query))
            filters_applied.append(f"Поиск: '{query}'")

        # Поиск по хештегам
        if tag_filter:
            search_query = Q(tags__name__iexact=tag_filter)
            filters_applied.append(f"Тег: '{tag_filter}'")

        # Базовая фильтрация - для обычных пользователей только опубликованные
        if request.user.is_authenticated and (request.user.is_staff or
                                              request.user.groups.filter(
                                                  name__in=['Модератор', 'Администратор']).exists()):
            # Админы/модераторы видят все статусы
            results = Article.objects.all()
        else:
            # Обычные пользователи - только опубликованные
            results = Article.objects.filter(status='published')

        # Применяем поисковый запрос если есть query или tag_filter
        if query or tag_filter:
            results = results.filter(search_query).distinct()

        # ФИЛЬТР ПО КАТЕГОРИИ
        if category_filter:
            results = results.filter(categories__slug=category_filter)
            try:
                category = Category.objects.get(slug=category_filter)
                filters_applied.append(f"Категория: {category.name}")
            except Category.DoesNotExist:
                pass

        # ФИЛЬТР ПО АВТОРУ
        if author_filter:
            results = results.filter(author__username__icontains=author_filter)
            filters_applied.append(f"Автор: '{author_filter}'")

        # ФИЛЬТР ПО СТАТУСУ (только для админов/модераторов)
        if status_filter and request.user.is_authenticated and (
                request.user.is_staff or request.user.groups.filter(name__in=['Модератор', 'Администратор']).exists()):
            results = results.filter(status=status_filter)
            status_display = dict(Article.STATUS_CHOICES).get(status_filter, status_filter)
            filters_applied.append(f"Статус: {status_display}")

        # ФИЛЬТР ПО ВРЕМЕНИ
        if time_filter != 'all':
            now = timezone.now()
            if time_filter == 'today':
                start_date = now - timezone.timedelta(days=1)
                time_display = "сегодня"
            elif time_filter == 'week':
                start_date = now - timezone.timedelta(days=7)
                time_display = "за неделю"
            elif time_filter == 'month':
                start_date = now - timezone.timedelta(days=30)
                time_display = "за месяц"
            elif time_filter == 'year':
                start_date = now - timezone.timedelta(days=365)
                time_display = "за год"
            else:
                start_date = None
                time_display = ""

            if start_date:
                results = results.filter(created_at__gte=start_date)
                filters_applied.append(f"Период: {time_display}")

        # ФИЛЬТР ПО МИНИМАЛЬНОМУ КОЛИЧЕСТВУ ПРОСМОТРОВ
        if min_views and min_views.isdigit():
            results = results.filter(views_count__gte=int(min_views))
            filters_applied.append(f"Просмотров: >{min_views}")

        # ФИЛЬТР ПО МИНИМАЛЬНОМУ КОЛИЧЕСТВУ ЛАЙКОВ
        if min_likes and min_likes.isdigit():
            results = results.annotate(likes_count=Count('likes')).filter(likes_count__gte=int(min_likes))
            filters_applied.append(f"Лайков: >{min_likes}")

        # ФИЛЬТР ПО НАЛИЧИЮ МЕДИА
        if has_media == 'yes':
            results = results.filter(media_files__isnull=False).distinct()
            filters_applied.append("С медиафайлами")

        # ФИЛЬТР ПО ДЛИНЕ СТАТЬИ
        if article_length:
            if article_length == 'short':
                results = results.annotate(content_length=Length('content')).filter(content_length__lt=1000)
                filters_applied.append("Короткие (<1000 символов)")
            elif article_length == 'medium':
                results = results.annotate(content_length=Length('content')).filter(
                    content_length__gte=1000, content_length__lt=5000
                )
                filters_applied.append("Средние (1000-5000 символов)")
            elif article_length == 'long':
                results = results.annotate(content_length=Length('content')).filter(content_length__gte=5000)
                filters_applied.append("Длинные (>5000 символов)")

        total_count = results.count()

        # Обновляем количество результатов в истории поиска
        if query and request.user.is_authenticated:
            last_search = SearchHistory.objects.filter(
                query=query,
                user=request.user
            ).order_by('-created_at').first()
            if last_search:
                last_search.results_count = total_count
                last_search.save()

        # УЛУЧШЕННАЯ СОРТИРОВКА
        if sort_by == 'date_new':
            results = results.order_by('-created_at')
            sort_display = "Сначала новые"
        elif sort_by == 'date_old':
            results = results.order_by('created_at')
            sort_display = "Сначала старые"
        elif sort_by == 'views':
            results = results.order_by('-views_count')
            sort_display = "По популярности"
        elif sort_by == 'likes':
            results = results.annotate(likes_count=Count('likes')).order_by('-likes_count')
            sort_display = "По лайкам"
        elif sort_by == 'comments':
            results = results.annotate(comments_count=Count('comments')).order_by('-comments_count')
            sort_display = "По комментариям"
        elif sort_by == 'title_asc':
            results = results.order_by('title')
            sort_display = "По названию (А-Я)"
        elif sort_by == 'title_desc':
            results = results.order_by('-title')
            sort_display = "По названию (Я-А)"
        else:  # relevance
            if query and not tag_filter:
                # Статьи с точным совпадением в названии (высший приоритет)
                exact_title_matches = results.filter(title__iexact=query)

                # Статьи с совпадением в начале названия
                start_title_matches = results.filter(title__istartswith=query).exclude(title__iexact=query)

                # Статьи с совпадением в названии (любая позиция)
                any_title_matches = results.filter(title__icontains=query).exclude(
                    title__istartswith=query
                ).exclude(title__iexact=query)

                # Статьи с совпадением только в контенте (низший приоритет)
                content_only_matches = results.filter(
                    content__icontains=query
                ).exclude(
                    Q(title__icontains=query) | Q(excerpt__icontains=query)
                )

                # Объединяем результаты с приоритетом
                results = list(exact_title_matches) + list(start_title_matches) + \
                          list(any_title_matches) + list(content_only_matches)
                sort_display = "По релевантности"
            else:
                results = results.order_by('-created_at')
                sort_display = "По дате"

        if sort_display and sort_display not in [f.split(": ")[1] if ": " in f else f for f in filters_applied]:
            filters_applied.append(f"Сортировка: {sort_display}")

        # Пагинация
        paginator = Paginator(results, 15)  # Увеличим до 15 на страницу
        page_number = request.GET.get('page')
        results = paginator.get_page(page_number)

    # Получаем популярные запросы (топ-10)
    popular_queries = SearchQuery.objects.all().order_by('-count')[:10]

    # Получаем недавние запросы пользователя
    recent_user_searches = []
    if request.user.is_authenticated:
        recent_user_searches = SearchHistory.objects.filter(
            user=request.user
        ).order_by('-created_at')[:10]

    # Получаем популярные хештеги
    from django.db.models import Count
    popular_tags = Article.tags.most_common()[:20]

    # Получаем категории для фильтра
    categories = Category.objects.all()

    # Получаем авторов для фильтра
    authors = User.objects.filter(
        articles__status='published'
    ).distinct().order_by('username')[:50]

    # Опции для селектов
    sort_options = [
        ('relevance', 'По релевантности'),
        ('date_new', 'Сначала новые'),
        ('date_old', 'Сначала старые'),
        ('views', 'По просмотрам'),
        ('likes', 'По лайкам'),
        ('comments', 'По комментариям'),
        ('title_asc', 'По названию (А-Я)'),
        ('title_desc', 'По названию (Я-А)'),
    ]

    time_options = [
        ('all', 'За всё время'),
        ('today', 'Сегодня'),
        ('week', 'За неделю'),
        ('month', 'За месяц'),
        ('year', 'За год'),
    ]

    status_options = Article.STATUS_CHOICES

    length_options = [
        ('', 'Любая длина'),
        ('short', 'Короткие (<1000 симв.)'),
        ('medium', 'Средние (1000-5000)'),
        ('long', 'Длинные (>5000 симв.)'),
    ]

    context = {
        'query': query,
        'category_filter': category_filter,
        'tag_filter': tag_filter,
        'author_filter': author_filter,
        'status_filter': status_filter,
        'sort_by': sort_by,
        'time_filter': time_filter,
        'min_views': min_views,
        'min_likes': min_likes,
        'has_media': has_media,
        'article_length': article_length,
        'results': results,
        'total_count': total_count,
        'filters_applied': filters_applied,
        'categories': categories,
        'authors': authors,
        'popular_queries': popular_queries,
        'recent_user_searches': recent_user_searches,
        'popular_tags': popular_tags,
        'sort_options': sort_options,
        'time_options': time_options,
        'status_options': status_options,
        'length_options': length_options,
        'user_can_moderate': request.user.is_authenticated and (
                request.user.is_staff or
                request.user.groups.filter(name__in=['Модератор', 'Администратор']).exists()
        ),
    }
    return render(request, 'wiki/search.html', context)


@login_required
def profile(request):
    """Страница профиля пользователя с возможностью редактирования"""
    user = request.user
    # Получаем или создаем профиль пользователя
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    user_comment_likes_count = CommentLike.objects.filter(user=request.user).count()
    user_comments_liked_count = Comment.objects.filter(comment_likes__user=user).distinct().count()

    # Обработка POST запросов из формы
    if request.method == 'POST':

        # Обработка обновления аватара
        if 'update_avatar' in request.POST and request.FILES.get('avatar'):
            user_profile.avatar = request.FILES['avatar']
            user_profile.save()
            messages.success(request, '✅ Аватар обновлен!')
            return redirect('wiki:profile')

        # Обработка обновления профиля
        elif 'update_profile' in request.POST:
            user_profile.vk = request.POST.get('vk', '')
            user_profile.telegram = request.POST.get('telegram', '')
            user_profile.discord = request.POST.get('discord', '')
            user_profile.youtube = request.POST.get('youtube', '')
            user_profile.bio = request.POST.get('bio', '')
            user_profile.save()
            messages.success(request, '✅ Настройки профиля сохранены!')
            return redirect('wiki:profile')

    # Статистика пользователя - ИСПРАВЛЕННЫЕ ЗАПРОСЫ
    user_articles_count = Article.objects.filter(author=request.user).count()
    published_articles_count = Article.objects.filter(author=request.user, status='published').count()

    # Исправленный запрос для лайков
    liked_articles_count = ArticleLike.objects.filter(user=request.user).count()

    # Исправленный запрос для просмотров
    total_views = Article.objects.filter(author=request.user).aggregate(
        total_views=Sum('views_count')
    )['total_views'] or 0

    # Последние статьи (все статусы)
    recent_articles = Article.objects.filter(author=request.user).order_by('-created_at')[:5]


    context = {
        'user': request.user,
        'user_profile': user_profile,
        'user_articles_count': user_articles_count,
        'published_articles_count': published_articles_count,
        'liked_articles_count': liked_articles_count,
        'total_views': total_views,
        'recent_articles': recent_articles,
        'user_comment_likes_count': user_comment_likes_count,
        'user_comments_liked_count': user_comments_liked_count,
        'TELEGRAM_BOT_USERNAME': getattr(settings, 'TELEGRAM_BOT_USERNAME', ''),
    }

    return render(request, 'accounts/profile.html', context)


@login_required
def article_create(request):
    """Создание новой статьи"""

    active_bans = UserBan.objects.filter(
        user=request.user,
        is_active=True
    )

    for ban in active_bans:
        if ban.duration == 'permanent' or (ban.expires_at and ban.expires_at > timezone.now()):
            messages.error(request, '❌ Вы не можете создавать статьи: ваш аккаунт заблокирован.')
            return redirect('banned_page')

    # ПРОВЕРКА 2: Есть ли 4+ предупреждений (даже если нет бана еще)
    warnings_count = UserWarning.objects.filter(
        user=request.user,
        is_active=True
    ).count()

    if warnings_count >= 4:
        messages.error(request,
                       f'❌ Вы не можете создавать статьи: у вас {warnings_count} активных предупреждений. '
                       f'Ожидается автоматический бан.'
                       )
        return redirect('wiki:home')

    # ПРОВЕРКА 3: Нецензурная лексика (дополнительная проверка на случай если middleware не сработал)
    if request.method == 'POST':
        banned_words = ['хуй', 'пизда', 'еблан', 'мудак', 'говно']
        found_words = []

        # Проверяем заголовок и контент
        title = request.POST.get('title', '')
        content = request.POST.get('content', '')

        for word in banned_words:
            if word in title.lower() or word in content.lower():
                found_words.append(word)

        if found_words:
            messages.error(request,
                           f'❌ Текст содержит запрещенные слова: {", ".join(found_words)}. '
                           f'Создание статьи заблокировано.'
                           )

            # Возвращаем форму с ошибкой
            categories = Category.objects.all()
            return render(request, 'wiki/article_create.html', {
                'categories': categories,
                'error_message': 'Текст содержит запрещенные слова'
            })
    error_message = ""
    success_message = ""

    # Проверяем, принял ли пользователь правила через параметр URL
    rules_accepted_param = request.GET.get('rules_accepted') == 'true'

    # Проверяем сессию и localStorage
    rules_accepted_session = request.session.get('article_rules_accepted', False)

    if request.method == 'POST':
        has_banned, banned_words = check_request_for_banned_words(request)
        if has_banned:
            add_censorship_warning(request, banned_words)

    # Если правила приняты через параметр, сохраняем в сессии
    if rules_accepted_param and not rules_accepted_session:
        request.session['article_rules_accepted'] = True
        request.session.set_expiry(60 * 60 * 24 * 30)  # 30 дней
        rules_accepted_session = True

    # Если правила не приняты, показываем страницу с правилами
    if request.method == 'GET' and not rules_accepted_session:
        return render(request, 'wiki/article_create_rules.html')

    if request.method == 'POST':
        # Проверяем, что правила приняты
        if not rules_accepted_session and not request.POST.get('rules_accepted'):
            messages.error(request, '❌ Для создания статьи необходимо принять правила.')
            return render(request, 'wiki/article_create_rules.html')

        # Если правила приняты через форму, сохраняем в сессии
        if request.POST.get('rules_accepted'):
            request.session['article_rules_accepted'] = True
            request.session.set_expiry(60 * 60 * 24 * 30)  # 30 дней
            rules_accepted_session = True

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        excerpt = request.POST.get('excerpt', '').strip()
        category_ids = request.POST.getlist('categories')
        tags_input = request.POST.get('tags', '').strip()
        form = ArticleForm(request.POST, request.FILES)

        # Проверка обязательных полей
        if not title or not content:
            error_message = "Пожалуйста, заполните заголовок и содержание статьи."
        elif not category_ids:
            error_message = "Пожалуйста, выберите хотя бы одну категорию."
        else:
            # Очищаем контент от LaTeX
            content = clean_latex_from_content(content)
            excerpt = clean_latex_from_content(excerpt)

            # Упрощенная проверка - только is_staff
            if request.user.is_staff:
                status = 'published'  # Админы публикуют сразу
            else:
                status = 'review'  # Обычные пользователи отправляют на модерацию

            # Создаем slug из заголовка
            try:
                from unidecode import unidecode
                slug = slugify(unidecode(title))
            except ImportError:
                # Простая транслитерация если unidecode не установлен
                translit_dict = {
                    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
                    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
                    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
                    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
                    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
                }
                title_lower = title.lower()
                for ru, en in translit_dict.items():
                    title_lower = title_lower.replace(ru, en)
                slug = slugify(title_lower)

            # Проверяем уникальность slug
            if Article.objects.filter(slug=slug).exists():
                counter = 1
                original_slug = slug
                while Article.objects.filter(slug=slug).exists():
                    slug = f"{original_slug}-{counter}"
                    counter += 1

            tags_list = []
            if tags_input:
                tags_list = [tag.strip().lower() for tag in tags_input.split(',') if tag.strip()]

            # Создаем статью
            article = Article(
                title=title,
                content=content,
                excerpt=excerpt,
                slug=slug,
                author=request.user,
                status=status
            )
            article.save()
            log_article_creation(request, article)
            ActionLogger.log_action(
                request=request,
                action_type='article_create',
                description=f'Пользователь {request.user.username} создал статью "{article.title}"',
                target_object=article,
                extra_data={
                    'article_title': article.title,
                    'article_slug': article.slug,
                    'status': article.status,
                    'categories_count': len(category_ids),
                    'tags_count': len(tags_list) if tags_input else 0,
                }
            )
            # Добавляем категории
            categories = Category.objects.filter(id__in=category_ids)
            article.categories.set(categories)

            # Добавляем хештеги (tags_list уже определен)
            for tag_name in tags_list:
                article.tags.add(tag_name)

            # Обрабатываем загруженные медиафайлы
            media_files = request.FILES.getlist('media_files')
            for media_file in media_files:
                if media_file:
                    # Определяем тип файла
                    file_name = media_file.name.lower()
                    if any(ext in file_name for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']):
                        file_type = 'image'
                    elif any(ext in file_name for ext in ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm']):
                        file_type = 'video'
                    elif any(ext in file_name for ext in ['.mp3', '.wav', '.ogg', '.flac']):
                        file_type = 'audio'
                    else:
                        file_type = 'document'

                    ArticleMedia.objects.create(
                        article=article,
                        file=media_file,
                        file_type=file_type,
                        title=media_file.name,
                        uploaded_by=request.user
                    )

            if status == 'review':
                success_message = "✅ Статья отправлена на модерацию. После проверки она будет опубликована."
                return render(request, 'wiki/article_create.html', {
                    'categories': Category.objects.all(),
                    'success_message': success_message
                })
            else:
                return redirect('wiki:article_detail', slug=article.slug)

    # Получаем все категории для формы
    categories = Category.objects.all()

    context = {
        'categories': categories,
        'error_message': error_message,
        'success_message': success_message,
    }
    return render(request, 'wiki/article_create.html', context)

def article_detail(request, slug):
    print(f"DEBUG: article_detail called for slug: {slug}")
    print(f"DEBUG: User authenticated: {request.user.is_authenticated}")
    print(f"DEBUG: User: {request.user}")
    article = get_object_or_404(Article, slug=slug)

    # Проверяем авторизацию пользователя - ИСПРАВЛЕННАЯ ПРОВЕРКА
    if not request.user.is_authenticated:
        print(f"DEBUG: User not authenticated, redirecting to login")
        messages.warning(request, 'Для просмотра статей необходимо авторизоваться.')
        # Используем reverse для получения URL
        login_url = reverse('wiki:login')
        return redirect(f'{login_url}?next={request.path}')

    # Проверяем права на просмотр
    if article.status != 'published' and not article.can_edit(request.user) and not (
            request.user.is_staff or request.user.groups.filter(name__in=['Модератор', 'Администратор']).exists()):
        return render(request, 'wiki/access_denied.html', {
            'message': 'У вас нет прав для просмотра этой статьи.'
        })
    print(f"DEBUG: User is authenticated, proceeding to article")
    # Увеличиваем счетчик просмотров только для опубликованных статей
    if article.status == 'published' and hasattr(article, 'views_count'):
        article.views_count += 1
        article.save(update_fields=['views_count'])

    # Получаем медиафайлы статьи с сортировкой
    media_files = article.media_files.all().order_by('display_order', 'uploaded_at')

    # Получаем комментарии к статье
    comments = article.comments.filter(is_deleted=False, parent__isnull=True)\
                               .order_by('created_at')\
                               .select_related('author')\
                               .prefetch_related('comment_likes')

    # Форма для добавления комментария
    comment_form = CommentForm()

    # Обработка добавления комментария
    if request.method == 'POST' and request.user.is_authenticated:
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.article = article
            comment.author = request.user

            # Обработка родительского комментария (для ответов)
            parent_id = request.POST.get('parent_id')
            if parent_id:
                try:
                    parent_comment = Comment.objects.get(id=parent_id)
                    comment.parent = parent_comment
                except Comment.DoesNotExist:
                    pass

            comment.save()
            messages.success(request, 'Комментарий добавлен!')
            return redirect('wiki:article_detail', slug=article.slug)
        else:
            messages.error(request, 'Ошибка при добавлении комментария. Проверьте форму.')

    context = {
        'article': article,
        'media_files': media_files,
        'comments': comments,
        'comment_form': comment_form,
        'can_edit': article.can_edit(request.user),
        'can_moderate': request.user.is_staff or request.user.groups.filter(name__in=['Модератор', 'Администратор']).exists(),
    }
    return render(request, 'wiki/article_detail.html', context)


@login_required
def article_edit(request, slug):
    """Редактирование статьи"""
    article = get_object_or_404(Article, slug=slug)

    if not article.can_edit(request.user):
        return render(request, 'wiki/access_denied.html', {
            'message': 'У вас нет прав для редактирования этой статьи.'
        })

    # СОХРАНЯЕМ СТАРОЕ НАЗВАНИЕ ПЕРЕД ОБРАБОТКОЙ ФОРМЫ
    old_title = article.title
    old_status = article.status  # Сохраняем старый статус для логирования

    ActionLogger.log_action(
        request=request,
        action_type='article_edit_start',
        description=f'Пользователь {request.user.username} начал редактирование статьи "{article.title}"',
        target_object=article
    )

    error_message = ""
    success_message = ""

    if request.method == 'POST':
        has_banned, banned_words = check_request_for_banned_words(request)
        if has_banned:
            add_censorship_warning(request, banned_words)

    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES, request=request)
        # Проверяем, это отправка на модерацию или сохранение
        action = request.POST.get('action', 'save')

        if action == 'submit_moderation':
            # Отправка на модерацию
            if article.submit_for_moderation():
                messages.success(request, '✅ Статья отправлена на модерацию!')
                return redirect('wiki:my_articles')
            else:
                messages.error(request, '❌ Не удалось отправить статью на модерацию.')

        else:
            # Обычное сохранение
            title = request.POST.get('title', '').strip()
            content = request.POST.get('content', '').strip()
            excerpt = request.POST.get('excerpt', '').strip()
            category_ids = request.POST.getlist('categories')

            # Очищаем контент от LaTeX
            content = clean_latex_from_content(content)
            excerpt = clean_latex_from_content(excerpt)

            if title and content:
                article.title = title
                article.content = content
                article.excerpt = excerpt

                # ЛОГИРОВАНИЕ С ИСПОЛЬЗОВАНИЕМ old_title
                ActionLogger.log_action(
                    request=request,
                    action_type='article_edit',
                    description=f'Пользователь {request.user.username} отредактировал статью "{old_title}"',
                    target_object=article,
                    extra_data={
                        'old_title': old_title,
                        'new_title': title,
                        'status_changed': article.status != old_status,
                    }
                )

                # Если статья была отклонена, возвращаем ее на модерацию после редактирования
                if article.status == 'rejected':
                    article.status = 'review'
                    article.moderation_notes = ''
                    success_message = "Статья отправлена на повторную модерацию."

                article.save()

                # Обновляем категории
                if category_ids:
                    categories = Category.objects.filter(id__in=category_ids)
                    article.categories.set(categories)
                else:
                    article.categories.clear()

                # Обрабатываем загруженные медиафайлы
                media_files = request.FILES.getlist('media_files')
                for media_file in media_files:
                    if media_file:
                        # Определяем тип файла
                        file_name = media_file.name.lower()
                        if any(ext in file_name for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']):
                            file_type = 'image'
                        elif any(ext in file_name for ext in ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm']):
                            file_type = 'video'
                        elif any(ext in file_name for ext in ['.mp3', '.wav', '.ogg', '.flac']):
                            file_type = 'audio'
                        else:
                            file_type = 'document'

                        ArticleMedia.objects.create(
                            article=article,
                            file=media_file,
                            file_type=file_type,
                            title=media_file.name,
                            uploaded_by=request.user
                        )

                messages.success(request, '✅ Изменения сохранены!')
                return redirect('wiki:article_detail', slug=article.slug)
            else:
                error_message = "Пожалуйста, заполните все обязательные поля."

    # Получаем все категории для формы
    categories = Category.objects.all()
    media_files = article.media_files.all()

    context = {
        'article': article,
        'categories': categories,
        'media_files': media_files,
        'error_message': error_message,
        'success_message': success_message,
    }
    return render(request, 'wiki/article_edit.html', context)


@login_required
def clean_all_articles_latex(request):
    """
    Админская функция для очистки LaTeX из всех статей
    Только для администраторов
    """
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Только для администраторов'})

    try:
        articles_updated = 0
        articles = Article.objects.all()

        for article in articles:
            original_content = article.content
            cleaned_content = clean_latex_from_content(original_content)

            if original_content != cleaned_content:
                article.content = cleaned_content
                article.save(update_fields=['content'])
                articles_updated += 1

        return JsonResponse({
            'success': True,
            'message': f'Очищено {articles_updated} статей от LaTeX-кода'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def article_moderate(request, slug):
    """Расширенная модерация статьи с возможностью выделения текста"""
    article = get_object_or_404(Article, slug=slug)

    if not (request.user.is_staff or request.user.groups.filter(name__in=['Модератор', 'Администратор']).exists()):
        return render(request, 'wiki/access_denied.html', {
            'message': 'У вас нет прав для модерации статей.'
        })

    if request.method == 'POST':
        action = request.POST.get('action')
        moderation_notes = request.POST.get('moderation_notes', '').strip()
        highlighted_corrections = request.POST.get('highlighted_corrections', '')

        log_article_moderation(request, article, action, moderation_notes)

        if action == 'approve':
            article.status = 'published'
            article.published_at = timezone.now()
            article.moderated_by = request.user
            article.moderated_at = timezone.now()
            article.moderation_notes = moderation_notes
            article.save()

            # Отправка уведомления автору
            send_moderation_notification(article, 'approved')
            messages.success(request, f'Статья "{article.title}" одобрена и опубликована.')

        elif action == 'needs_correction':
            article.status = 'needs_correction'
            article.moderated_by = request.user
            article.moderated_at = timezone.now()
            article.moderation_notes = moderation_notes

            # Сохраняем выделенные правки если есть
            if highlighted_corrections:
                try:
                    article.highlighted_corrections = json.loads(highlighted_corrections)
                except json.JSONDecodeError:
                    pass

            # Устанавливаем срок исправления (7 дней по умолчанию)
            article.correction_deadline = timezone.now() + timezone.timedelta(days=7)
            article.save()

            # Отправка уведомления автору
            send_moderation_notification(article, 'needs_correction')
            messages.success(request, f'Статья "{article.title}" отправлена на доработку.')

        elif action == 'send_to_editor':
            article.status = 'editor_review'
            article.moderated_by = request.user
            article.moderated_at = timezone.now()
            article.moderation_notes = moderation_notes

            if highlighted_corrections:
                try:
                    article.highlighted_corrections = json.loads(highlighted_corrections)
                except json.JSONDecodeError:
                    pass

            article.save()
            messages.success(request, f'Статья "{article.title}" отправлена редактору.')

        return redirect('wiki:moderation_queue')

    # Получаем существующие комментарии модерации
    moderation_comments = article.moderation_comments.all().order_by('-created_at')

    context = {
        'article': article,
        'moderation_comments': moderation_comments,
    }
    return render(request, 'wiki/article_moderate_enhanced.html', context)


@login_required
def add_moderation_comment(request, slug):
    """Добавление комментария к выделенному тексту"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        article = get_object_or_404(Article, slug=slug)

        if not (request.user.is_staff or request.user.groups.filter(name__in=['Модератор', 'Администратор']).exists()):
            return JsonResponse({'success': False, 'error': 'Нет прав для модерации'})

        highlighted_text = request.POST.get('highlighted_text', '')
        comment = request.POST.get('comment', '')
        start_pos = request.POST.get('start_position', 0)
        end_pos = request.POST.get('end_position', 0)

        if highlighted_text and comment:
            moderation_comment = ModerationComment.objects.create(
                article=article,
                moderator=request.user,
                highlighted_text=highlighted_text,
                comment=comment,
                start_position=start_pos,
                end_position=end_pos
            )

            return JsonResponse({
                'success': True,
                'comment_id': moderation_comment.id,
                'created_at': moderation_comment.created_at.strftime('%d.%m.%Y %H:%M')
            })

    return JsonResponse({'success': False, 'error': 'Неверный запрос'})


@login_required
def editor_review(request, slug):
    """Страница для редактора"""
    article = get_object_or_404(Article, slug=slug)

    # Проверяем права редактора
    if not (request.user.is_staff or
            request.user.groups.filter(name__in=['Редактор', 'Модератор', 'Администратор']).exists()):
        return render(request, 'wiki/access_denied.html', {
            'message': 'У вас нет прав редактора.'
        })

    if request.method == 'POST':
        corrected_content = request.POST.get('corrected_content', '')
        editor_notes = request.POST.get('editor_notes', '')

        if corrected_content:
            # Сохраняем исправленную версию
            article.content = corrected_content
            article.editor_notes = editor_notes
            article.status = 'author_review'
            article.save()

            # Отправляем уведомление автору
            send_moderation_notification(article, 'editor_correction')
            messages.success(request, 'Исправленная версия отправлена автору на согласование.')
            return redirect('wiki:moderation_queue')

    context = {
        'article': article,
    }
    return render(request, 'wiki/editor_review.html', context)


@login_required
def author_review(request, slug):
    """Страница для автора - согласование исправлений"""
    article = get_object_or_404(Article, slug=slug)

    # Проверяем права автора и статус статьи
    if not article.can_accept_revisions(request.user):
        return render(request, 'wiki/access_denied.html', {
            'message': 'У вас нет прав для согласования правок этой статьи.'
        })

    if request.method == 'POST':
        action = request.POST.get('action')
        author_notes = request.POST.get('author_notes', '').strip()

        if action == 'accept':
            article.accept_editor_revisions()
            messages.success(request, '✅ Статья опубликована с исправлениями редактора.')

        elif action == 'reject':
            if not author_notes:
                messages.error(request, '❌ Пожалуйста, укажите причину отклонения правок.')
                context = {
                    'article': article,
                    'author_notes': author_notes,
                }
                return render(request, 'wiki/author_review.html', context)

            article.reject_editor_revisions(author_notes)
            messages.success(request, '📝 Исправления отклонены. Статья возвращена в черновики для доработки.')

        elif action == 'edit':
            # Автор хочет самостоятельно редактировать статью
            article.status = 'draft'
            article.author_notes = author_notes
            article.save()
            messages.success(request, '✏️ Статья возвращена в черновики для самостоятельного редактирования.')
            return redirect('wiki:article_edit', slug=article.slug)

        return redirect('wiki:my_articles')

    # Получаем историю изменений если есть
    revisions = article.revisions.all().order_by('-created_at')[:5]

    context = {
        'article': article,
        'revisions': revisions,
    }
    return render(request, 'wiki/author_review.html', context)

@login_required
def delete_media(request, media_id):
    """Удаление медиафайла"""
    media = get_object_or_404(ArticleMedia, id=media_id)

    if not media.article.can_edit(request.user):
        return JsonResponse({'success': False, 'error': 'Нет прав для удаления медиафайла'})

    try:
        media_file_path = media.file.path
        media.delete()

        # Удаляем физический файл
        if os.path.exists(media_file_path):
            os.remove(media_file_path)

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def category_create(request):
    """Создание новой категории"""
    if not (request.user.is_staff or
            request.user.groups.filter(name__in=['Модератор', 'Администратор']).exists()):
        return JsonResponse({'success': False, 'error': 'Нет прав для создания категорий'})

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        parent_id = request.POST.get('parent', '')
        is_featured = request.POST.get('is_featured') == 'true'
        display_order = request.POST.get('display_order', 0)
        icon = request.POST.get('icon', '').strip()

        if not name:
            return JsonResponse({'success': False, 'error': 'Название категории обязательно'})

        try:
            # Создаем slug из названия
            slug = slugify(name)
            if Category.objects.filter(slug=slug).exists():
                counter = 1
                original_slug = slug
                while Category.objects.filter(slug=slug).exists():
                    slug = f"{original_slug}-{counter}"
                    counter += 1

            category = Category(
                name=name,
                slug=slug,
                description=description,
                is_featured=is_featured,
                display_order=display_order,
                icon=icon
            )

            if parent_id:
                parent = Category.objects.get(id=parent_id)
                category.parent = parent

            category.save()
            ActionLogger.log_action(
                request=request,
                action_type='category_create',
                description=f'Пользователь {request.user.username} создал категорию "{name}"',
                target_object=category,
                extra_data={
                    'category_name': name,
                    'is_featured': is_featured,
                    'has_parent': bool(parent_id),
                }
            )
            return JsonResponse({
                'success': True,
                'category': {
                    'id': category.id,
                    'name': category.name,
                    'slug': category.slug,
                    'description': category.description,
                    'is_featured': category.is_featured,
                    'display_order': category.display_order,
                    'icon': category.icon,
                    'parent': category.parent.name if category.parent else None,
                    'article_count': 0,
                    'children_count': 0
                }
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Неверный метод запроса'})


@login_required
def category_edit(request, category_id):
    """Редактирование категории"""
    if not (request.user.is_staff or
            request.user.groups.filter(name__in=['Модератор', 'Администратор']).exists()):
        return JsonResponse({'success': False, 'error': 'Нет прав для редактирования категорий'})

    category = get_object_or_404(Category, id=category_id)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        parent_id = request.POST.get('parent', '')
        is_featured = request.POST.get('is_featured') == 'true'
        display_order = request.POST.get('display_order', 0)
        icon = request.POST.get('icon', '').strip()

        if not name:
            return JsonResponse({'success': False, 'error': 'Название категории обязательно'})

        try:
            category.name = name
            category.description = description
            category.is_featured = is_featured
            category.display_order = display_order
            category.icon = icon

            if parent_id:
                parent = Category.objects.get(id=parent_id)
                category.parent = parent
            else:
                category.parent = None

            category.save()

            return JsonResponse({
                'success': True,
                'category': {
                    'id': category.id,
                    'name': category.name,
                    'slug': category.slug,
                    'description': category.description,
                    'is_featured': category.is_featured,
                    'display_order': category.display_order,
                    'icon': category.icon,
                    'parent': category.parent.name if category.parent else None
                }
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    # GET запрос - возвращаем данные категории
    return JsonResponse({
        'success': True,
        'category': {
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'is_featured': category.is_featured,
            'display_order': category.display_order,
            'icon': category.icon,
            'parent': category.parent.id if category.parent else None
        }
    })


@login_required
def category_delete(request, category_id):
    """Удаление категории"""
    if not (request.user.is_staff or
            request.user.groups.filter(name__in=['Модератор', 'Администратор']).exists()):
        return JsonResponse({'success': False, 'error': 'Нет прав для удаления категорий'})

    category = get_object_or_404(Category, id=category_id)

    # Проверяем, можно ли удалить категорию
    if category.articles.exists():
        return JsonResponse({
            'success': False,
            'error': 'Нельзя удалить категорию, в которой есть статьи. Перенесите статьи в другие категории.'
        })

    if category.children.exists():
        return JsonResponse({
            'success': False,
            'error': 'Нельзя удалить категорию, у которой есть подкатегории. Сначала удалите или переместите подкатегории.'
        })

    try:
        category_name = category.name
        category.delete()
        return JsonResponse({'success': True, 'message': f'Категория "{category_name}" удалена'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def category_toggle_featured(request, category_id):
    """Переключение статуса основной категории"""
    if not (request.user.is_staff or
            request.user.groups.filter(name__in=['Модератор', 'Администратор']).exists()):
        return JsonResponse({'success': False, 'error': 'Нет прав для изменения категорий'})

    category = get_object_or_404(Category, id=category_id)

    try:
        category.is_featured = not category.is_featured
        category.save()

        return JsonResponse({
            'success': True,
            'is_featured': category.is_featured,
            'message': f'Категория {"добавлена в" if category.is_featured else "убрана из"} основных'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def get_categories_json(request):
    """API для получения списка категорий в формате JSON"""
    categories = Category.objects.all().values('id', 'name', 'parent')
    return JsonResponse(list(categories), safe=False)


def register(request):
    """Упрощенная регистрация с подтверждением email"""
    if request.user.is_authenticated:
        return redirect('wiki:home')

    stage = request.session.get('reg_stage', 1)

    if request.method == 'POST':
        if stage == 1:
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            password1 = request.POST.get('password1', '')
            password2 = request.POST.get('password2', '')

            if not username or not email or not password1 or not password2:
                messages.error(request, '❌ Заполните все поля')
                return render(request, 'accounts/register.html', {'stage': 1})

            if User.objects.filter(username=username).exists():
                messages.error(request, '❌ Имя пользователя уже занято')
                return render(request, 'accounts/register.html', {'stage': 1})

            if User.objects.filter(email=email).exists():
                messages.error(request, '❌ Email уже используется')
                return render(request, 'accounts/register.html', {'stage': 1})

            if password1 != password2:
                messages.error(request, '❌ Пароли не совпадают')
                return render(request, 'accounts/register.html', {'stage': 1})

            if len(password1) < 8:
                messages.error(request, '❌ Пароль должен быть не менее 8 символов')
                return render(request, 'accounts/register.html', {'stage': 1})

            request.session['reg_data'] = {
                'username': username,
                'email': email,
                'password': password1
            }

            try:
                EmailVerification.objects.filter(
                    email=email,
                    purpose='registration',
                    is_used=False
                ).update(is_used=True)

                verification = EmailVerification.objects.create(
                    email=email,
                    purpose='registration'
                )

                subject = 'Код подтверждения регистрации'
                message = f'Ваш код подтверждения: {verification.code}'

                try:
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [email],
                        fail_silently=False,
                    )

                except Exception as mail_error:
                    messages.info(request, f'⚠️ Ошибка отправки email. Код для теста: {verification.code}')

                request.session['verification_id'] = verification.id
                request.session['reg_stage'] = 2

                messages.success(request, f'✅ Код отправлен на {email}')
                return redirect('wiki:register')

            except Exception as e:
                messages.error(request, f'❌ Ошибка: {str(e)}')
                return render(request, 'accounts/register.html', {'stage': 1})

        elif stage == 2:
            entered_code = request.POST.get('code', '').strip()

            reg_data = request.session.get('reg_data')
            verification_id = request.session.get('verification_id')

            if not reg_data or not verification_id:
                messages.error(request, '❌ Сессия истекла. Начните заново.')
                request.session.flush()
                return redirect('wiki:register')

            email = reg_data['email']
            username = reg_data['username']
            password = reg_data['password']

            try:
                verification = EmailVerification.objects.get(
                    id=verification_id,
                    email=email,
                    purpose='registration',
                    is_used=False
                )

                if verification.code != entered_code:
                    messages.error(request, '❌ Неверный код подтверждения')
                    return render(request, 'accounts/register.html', {'stage': 2})

                if not verification.is_valid():
                    messages.error(request, '❌ Код истек. Запросите новый.')
                    return render(request, 'accounts/register.html', {'stage': 2})

                try:
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        is_active=True
                    )

                    try:
                        profile = UserProfile.objects.get(user=user)
                    except UserProfile.DoesNotExist:
                        profile = UserProfile.objects.create(user=user)

                    profile.save()

                    # Помечаем код как использованный
                    verification.is_used = True
                    verification.save()

                    # Очищаем сессию
                    request.session.flush()

                    # Устанавливаем флаги для страницы входа
                    request.session['registration_success'] = True
                    request.session['registered_username'] = username

                    # Отправляем приветственное письмо (опционально)
                    try:
                        subject = 'Добро пожаловать на Форум Ведьмак!'
                        welcome_message = f'''
                        Добро пожаловать, {username}!

                        ✅ Ваш аккаунт успешно создан.
                        ✅ Email подтвержден.

                        Приятного использования форума!
                        '''

                        send_mail(
                            subject,
                            welcome_message,
                            settings.DEFAULT_FROM_EMAIL,
                            [email],
                            fail_silently=True,
                        )
                        print("=== ДЕБАГ: Приветственное письмо отправлено ===")
                    except Exception as mail_error:
                        print(f"=== ДЕБАГ: Ошибка отправки приветственного письма: {mail_error} ===")

                    # ✅ ПЕРЕНАПРАВЛЯЕМ НА СТРАНИЦУ ВХОДА
                    print("=== ДЕБАГ: Редирект на login ===")
                    return redirect('wiki:login')

                except Exception as user_error:
                    import traceback
                    traceback.print_exc()
                    messages.error(request, f'❌ Ошибка создания аккаунта: {str(user_error)}')
                    return render(request, 'accounts/register.html', {'stage': 2})

            except EmailVerification.DoesNotExist:
                messages.error(request, '❌ Неверный код подтверждения')
                return render(request, 'accounts/register.html', {'stage': 2})

            except Exception as e:
                import traceback
                traceback.print_exc()
                messages.error(request, f'❌ Ошибка: {str(e)}')
                return render(request, 'accounts/register.html', {'stage': 2})

    else:
        # GET запрос - сбрасываем если пользователь вернулся на страницу
        if 'reset' in request.GET:
            request.session.flush()
            stage = 1

    # Получаем данные для отображения
    reg_data = request.session.get('reg_data', {})
    email = reg_data.get('email', '')
    username = reg_data.get('username', '')

    context = {
        'stage': stage,
        'email': email,
        'username': username,
        'form_data': reg_data
    }

    return render(request, 'accounts/register.html', context)


def user_public_profile(request, username):
    """Публичный профиль пользователя"""
    user = get_object_or_404(User, username=username)

    # Получаем профиль пользователя
    try:
        user_profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        user_profile = None

    if request.method == 'POST':
        has_banned, banned_words = check_request_for_banned_words(request)
        if has_banned:
            add_censorship_warning(request, banned_words)

    # Статьи пользователя (только опубликованные)
    user_articles = Article.objects.filter(author=user, status='published').order_by('-created_at')

    # Статистика
    articles_count = user_articles.count()

    context = {
        'profile_user': user,
        'user_profile': user_profile,
        'user_articles': user_articles,
        'articles_count': articles_count,
    }
    return render(request, 'wiki/user_public_profile.html', context)


@login_required
def toggle_article_like(request, slug):
    """Добавляет/убирает лайк статьи"""
    article = get_object_or_404(Article, slug=slug)

    if request.method == 'POST':
        try:
            # Проверяем, был ли уже лайк от пользователя
            was_liked = article.is_liked_by_user(request.user)

            # Переключаем лайк
            liked = article.toggle_like(request.user)
            likes_count = article.get_likes_count()
            action = 'article_like_add' if liked else 'article_like_remove'
            description = f'Пользователь {request.user.username} {"поставил" if liked else "убрал"} лайк статье "{article.title}"'

            ActionLogger.log_action(
                request=request,
                action_type=action,
                description=description,
                target_object=article,
                extra_data={
                    'article_title': article.title,
                    'was_liked': was_liked,
                    'now_liked': liked,
                    'total_likes': likes_count,
                }
            )
            return JsonResponse({
                'success': True,
                'liked': liked,
                'likes_count': likes_count,
                'was_liked': was_liked,  # Добавляем информацию о предыдущем состоянии
                'status_changed': was_liked != liked  # Изменился ли статус лайка
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid method'})


@login_required
def liked_articles(request):
    """Страница с понравившимися статьями"""
    likes = ArticleLike.objects.filter(user=request.user).select_related('article')
    liked_articles_list = [like.article for like in likes if like.article.status == 'published']

    # Пагинация
    paginator = Paginator(liked_articles_list, 12)
    page_number = request.GET.get('page')
    articles = paginator.get_page(page_number)

    context = {
        'articles': articles,
        'total_count': len(liked_articles_list),
    }
    return render(request, 'wiki/liked_articles.html', context)


@login_required
def debug_test_like(request):
    """Простой тестовый endpoint"""
    return JsonResponse({
        'status': 'ok',
        'message': 'Debug endpoint works!',
        'method': request.method
    })


@login_required
def debug_article_like(request, slug):
    """Упрощенная версия лайков для отладки"""
    print(f"DEBUG: Like request for article slug: {slug}")  # Проверим в консоли Django

    if request.method == 'POST':
        try:
            article = Article.objects.get(slug=slug)
            liked = article.toggle_like(request.user)
            likes_count = article.get_likes_count()

            return JsonResponse({
                'success': True,
                'liked': liked,
                'likes_count': likes_count,
                'debug_slug': slug
            })
        except Article.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'Article with slug {slug} not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

    return JsonResponse({'success': False, 'error': 'Only POST allowed'})
# В views.py ДОБАВИТЬ функцию my_articles (если её нет):

@login_required
def my_articles(request):
    """Статьи текущего пользователя"""
    articles = Article.objects.filter(author=request.user).order_by('-created_at')

    # Статистика по статусам
    stats = {
        'draft': articles.filter(status='draft').count(),
        'review': articles.filter(status='review').count(),
        'published': articles.filter(status='published').count(),
        'rejected': articles.filter(status='rejected').count(),
    }

    context = {
        'articles': articles,
        'stats': stats,
    }
    return render(request, 'wiki/my_articles.html', context)


# В views.py ДОБАВИТЬ эти функции:

@login_required
def add_moderation_comment(request, slug):
    """Добавление комментария к выделенному тексту"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        article = get_object_or_404(Article, slug=slug)

        if not (request.user.is_staff or request.user.groups.filter(name__in=['Модератор', 'Администратор']).exists()):
            return JsonResponse({'success': False, 'error': 'Нет прав для модерации'})

        highlighted_text = request.POST.get('highlighted_text', '')
        comment = request.POST.get('comment', '')
        start_pos = int(request.POST.get('start_position', 0))
        end_pos = int(request.POST.get('end_position', 0))

        if highlighted_text and comment:
            moderation_comment = ModerationComment.objects.create(
                article=article,
                moderator=request.user,
                highlighted_text=highlighted_text,
                comment=comment,
                start_position=start_pos,
                end_position=end_pos
            )

            return JsonResponse({
                'success': True,
                'comment_id': moderation_comment.id,
                'created_at': moderation_comment.created_at.strftime('%d.%m.%Y %H:%M')
            })

    return JsonResponse({'success': False, 'error': 'Неверный запрос'})


def send_moderation_notification(article, action_type):
    """Отправка уведомления автору о результате модерации"""
    # В реальном проекте здесь будет отправка email или уведомлений в системе
    # Пока просто логируем
    print(f"Уведомление для {article.author.username}: Статья '{article.title}' - {action_type}")


@login_required
def editor_review(request, slug):
    """Страница для редактора"""
    article = get_object_or_404(Article, slug=slug)

    # Проверяем права редактора
    if not (request.user.is_staff or
            request.user.groups.filter(name__in=['Редактор', 'Модератор', 'Администратор']).exists()):
        return render(request, 'wiki/access_denied.html', {
            'message': 'У вас нет прав редактора.'
        })

    if request.method == 'POST':
        corrected_content = request.POST.get('corrected_content', '')
        editor_notes = request.POST.get('editor_notes', '')

        if corrected_content:
            # Сохраняем исправленную версию
            article.content = corrected_content
            article.editor_notes = editor_notes
            article.status = 'author_review'
            article.save()

            # Отправляем уведомление автору
            send_moderation_notification(article, 'editor_correction')
            messages.success(request, 'Исправленная версия отправлена автору на согласование.')
            return redirect('wiki:moderation_queue')

    context = {
        'article': article,
    }
    return render(request, 'wiki/editor_review.html', context)


def can_moderate(user):
    """Проверяет, может ли пользователь модерировать статьи"""
    # Модераторы и админы
    return (user.is_staff or
            user.groups.filter(name__in=['Модератор', 'Администратор']).exists())

def can_edit_content(user):
    """Проверяет, может ли пользователь редактировать контент как редактор"""
    # ТОЛЬКО редакторы и админы, НЕ модераторы!
    return (user.is_staff or
            user.groups.filter(name__in=['Редактор', 'Администратор']).exists())

# Обновим функцию moderation_queue
@login_required
def moderation_queue(request):
    """Очередь статей на модерацию - только для модераторов"""
    if not user_can_moderate(request.user):
        return render(request, 'wiki/access_denied.html', {
            'message': 'У вас нет прав для модерации статей.'
        })

    # Статьи на модерации
    pending_articles = Article.objects.filter(status='review').order_by('-created_at')

    # Статьи для редактора
    editor_articles = Article.objects.filter(status='editor_review').order_by('-created_at')

    # Недавно отклоненные статьи
    rejected_articles = Article.objects.filter(status='rejected').order_by('-moderated_at')[:10]

    context = {
        'pending_articles': pending_articles,
        'editor_articles': editor_articles,
        'rejected_articles': rejected_articles,
        'user_can_moderate': user_can_moderate(request.user),
        'user_can_edit': user_can_edit_content(request.user),
    }
    return render(request, 'wiki/moderation_queue.html', context)

# Обновим функцию editor_review
@login_required
def editor_review(request, slug):
    """Страница для редактора - только для редакторов"""
    article = get_object_or_404(Article, slug=slug)

    # Проверяем права редактора
    if not can_edit_content(request.user):
        return render(request, 'wiki/access_denied.html', {
            'message': 'У вас нет прав редактора.'
        })

    if request.method == 'POST':
        corrected_content = request.POST.get('corrected_content', '')
        editor_notes = request.POST.get('editor_notes', '')

        if corrected_content:
            # Сохраняем исправленную версию
            article.content = corrected_content
            article.editor_notes = editor_notes
            article.status = 'author_review'
            article.save()

            # Отправляем уведомление автору
            send_moderation_notification(article, 'editor_correction')
            messages.success(request, 'Исправленная версия отправлена автору на согласование.')
            return redirect('wiki:moderation_queue')

    context = {
        'article': article,
    }
    return render(request, 'wiki/editor_review.html', context)

# Обновим функцию category_management
@login_required
def category_management(request):
    """Страница управления категориями - только для модераторов"""
    if not can_moderate(request.user):
        return render(request, 'wiki/access_denied.html', {
            'message': 'У вас нет прав для управления категориями.'
        })

    categories = Category.objects.all().annotate(
        article_count=Count('articles'),
        children_count=Count('children')
    ).order_by('display_order', 'name')

    context = {
        'categories': categories,
    }
    return render(request, 'wiki/category_management.html', context)


# views.py - ДОБАВИТЬ новую функцию
@login_required
def editor_dashboard(request):
    """Панель редактора - только для редакторов"""
    if not can_edit_content(request.user):
        return render(request, 'wiki/access_denied.html', {
            'message': 'У вас нет прав редактора.'
        })

    # Статьи для редактуры
    editor_articles = Article.objects.filter(status='editor_review').order_by('-created_at')

    # Статистика
    waiting_count = editor_articles.count()
    edited_count = Article.objects.filter(
        status='author_review',
        editor_notes__isnull=False
    ).count()

    context = {
        'editor_articles': editor_articles,
        'waiting_count': waiting_count,
        'edited_count': edited_count,
    }
    return render(request, 'wiki/editor_dashboard.html', context)

@login_required
def delete_comment(request, comment_id):
    """Удаление комментария"""
    comment = get_object_or_404(Comment, id=comment_id)

    # Проверяем права: автор комментария или модератор
    if comment.author != request.user and not comment.article.can_moderate(request.user):
        return JsonResponse({'success': False, 'error': 'Нет прав для удаления комментария'})

    try:
        comment.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def user_is_admin(user):
    """Проверяет, является ли пользователь администратором"""
    return user.is_staff or user.groups.filter(name='Администратор').exists()


@user_passes_test(user_is_admin)
def user_management(request):
    """Страница управления пользователями для администраторов"""
    users = User.objects.all().select_related('profile').prefetch_related('groups', 'articles')
    groups = Group.objects.all()

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        group_id = request.POST.get('group_id')
        action = request.POST.get('action')

        if user_id and group_id:
            try:
                user = User.objects.get(id=user_id)
                group = Group.objects.get(id=group_id)

                if action == 'add':
                    user.groups.add(group)
                    messages.success(request, f'✅ Пользователь {user.username} добавлен в группу {group.name}')
                elif action == 'remove':
                    user.groups.remove(group)
                    messages.success(request, f'🗑️ Пользователь {user.username} удален из группы {group.name}')

            except (User.DoesNotExist, Group.DoesNotExist):
                messages.error(request, '❌ Ошибка: пользователь или группа не найдены')

    # Статистика по группам
    group_stats = {}
    for group in groups:
        group_stats[group.name] = group.user_set.count()

    context = {
        'users': users,
        'groups': groups,
        'group_stats': group_stats,
    }

    # Если это AJAX запрос, возвращаем JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.core import serializers
        users_data = []
        for user in users:
            users_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'date_joined': user.date_joined.strftime('%d.%m.%Y'),
                'last_login': user.last_login.strftime('%d.%m.%Y %H:%M') if user.last_login else '—',
                'groups': [group.name for group in user.groups.all()],
                'articles_count': user.articles.count(),
                'avatar_url': user.profile.avatar.url if user.profile.avatar else None,
            })
        return JsonResponse({'users': users_data})

    return render(request, 'wiki/user_management.html', context)


@login_required
def messages_list(request, folder='inbox'):
    """Список сообщений пользователя"""
    if folder == 'inbox':
        messages = Message.objects.filter(
            recipient=request.user,
            recipient_deleted=False
        ).select_related('sender', 'recipient')
        title = 'Входящие сообщения'
    elif folder == 'sent':
        messages = Message.objects.filter(
            sender=request.user,
            sender_deleted=False
        ).select_related('sender', 'recipient')
        title = 'Отправленные сообщения'
    else:
        messages = Message.objects.none()
        title = 'Сообщения'

    # Пагинация
    paginator = Paginator(messages, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Подсчет непрочитанных
    unread_count = Message.objects.filter(
        recipient=request.user,
        is_read=False,
        recipient_deleted=False
    ).count()

    context = {
        'messages': page_obj,
        'title': title,
        'folder': folder,
        'unread_count': unread_count,
        'page_obj': page_obj,
    }
    return render(request, 'wiki/messages_list.html', context)


@login_required
def message_detail(request, message_id):
    """Просмотр конкретного сообщения"""
    message = get_object_or_404(Message, id=message_id)

    # Проверяем права доступа
    if not message.can_view(request.user):
        return render(request, 'wiki/access_denied.html', {
            'message': 'У вас нет прав для просмотра этого сообщения.'
        })

    # Помечаем как прочитанное если получатель
    if message.recipient == request.user and not message.is_read:
        message.mark_as_read()

    context = {
        'message': message,
    }
    return render(request, 'wiki/message_detail.html', context)


@login_required
def message_create(request, recipient_id=None):
    """Создание нового сообщения"""
    recipient = None
    if recipient_id:
        recipient = get_object_or_404(User, id=recipient_id)
        # Проверяем, что не отправляем себе
        if recipient == request.user:
            messages.error(request, 'Нельзя отправлять сообщение самому себе.')
            return redirect('wiki:messages_list')

    if request.method == 'POST':
        form = MessageForm(request.POST, sender=request.user)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            message.save()
            ActionLogger.log_action(
                request=request,
                action_type='message_send',
                description=f'Пользователь {request.user.username} отправил сообщение пользователю {message.recipient.username}',
                target_object=message,
                extra_data={
                    'recipient': message.recipient.username,
                    'subject': message.subject,
                    'message_length': len(message.content),
                }
            )
            messages.success(request, f'Сообщение отправлено пользователю {message.recipient.username}')
            return redirect('wiki:messages_list', folder='sent')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        initial = {}
        if recipient:
            initial['recipient'] = recipient
        form = MessageForm(initial=initial, sender=request.user)

    context = {
        'form': form,
        'recipient': recipient,
    }
    return render(request, 'wiki/message_create.html', context)


@login_required
def send_quick_message(request, user_id):
    """Быстрая отправка сообщения через AJAX"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        recipient = get_object_or_404(User, id=user_id)

        # Проверяем, что не отправляем себе
        if recipient == request.user:
            return JsonResponse({
                'success': False,
                'error': 'Нельзя отправлять сообщение самому себе.'
            })

        content = request.POST.get('content', '').strip()

        if not content:
            return JsonResponse({
                'success': False,
                'error': 'Введите текст сообщения.'
            })

        if len(content) > 1000:
            return JsonResponse({
                'success': False,
                'error': 'Сообщение слишком длинное (максимум 1000 символов).'
            })

        # Создаем сообщение
        message = Message.objects.create(
            sender=request.user,
            recipient=recipient,
            subject=f'Сообщение от {request.user.username}',
            content=content
        )

        return JsonResponse({
            'success': True,
            'message': 'Сообщение успешно отправлено!',
            'message_id': message.id
        })

    return JsonResponse({'success': False, 'error': 'Неверный запрос'})


@login_required
def message_delete(request, message_id):
    """Удаление сообщения"""
    message = get_object_or_404(Message, id=message_id)

    if not message.can_delete(request.user):
        return JsonResponse({'success': False, 'error': 'Нет прав для удаления сообщения'})

    if request.method == 'POST':
        # Помечаем сообщение как удаленное для текущего пользователя
        if request.user == message.sender:
            message.sender_deleted = True
        else:
            message.recipient_deleted = True

        message.save()

        # Если сообщение удалено обоими пользователями, удаляем его полностью
        if message.sender_deleted and message.recipient_deleted:
            message.delete()
            messages.success(request, 'Сообщение полностью удалено.')
        else:
            messages.success(request, 'Сообщение перемещено в корзину.')

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})

        return redirect('wiki:messages_list')

    return JsonResponse({'success': False, 'error': 'Неверный метод'})


@login_required
def get_unread_count(request):
    """Получение количества непрочитанных сообщений (для AJAX)"""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        count = Message.objects.filter(
            recipient=request.user,
            is_read=False,
            recipient_deleted=False
        ).count()
        return JsonResponse({'unread_count': count})

    return JsonResponse({'error': 'Invalid request'})


@login_required
def article_moderate_enhanced(request, slug):
    """Расширенная модерация статьи"""
    article = get_object_or_404(Article, slug=slug)

    if not user_can_moderate(request.user):
        return render(request, 'wiki/access_denied.html', {
            'message': 'У вас нет прав для модерации статей.'
        })

    if request.method == 'POST':
        action = request.POST.get('action')
        moderation_notes = request.POST.get('moderation_notes', '').strip()

        log_article_moderation(request, article, action, moderation_notes)
        if action == 'approve':
            # ✅ ОДОБРИТЬ - сразу публикуем
            article.status = 'published'
            article.published_at = timezone.now()
            article.moderated_by = request.user
            article.moderated_at = timezone.now()
            article.moderation_notes = moderation_notes
            article.save()

            send_moderation_notification(article, 'approved')
            messages.success(request, f'Статья "{article.title}" одобрена и опубликована.')
            return redirect('wiki:moderation_queue')

        elif action == 'needs_correction':
            # ❌ ОТКЛОНИТЬ - отправляем автору на исправление
            article.status = 'needs_correction'
            article.moderated_by = request.user
            article.moderated_at = timezone.now()
            article.moderation_notes = moderation_notes
            article.correction_deadline = timezone.now() + timezone.timedelta(days=7)
            article.save()

            send_moderation_notification(article, 'needs_correction')
            messages.success(request, f'Статья "{article.title}" отправлена автору на доработку.')
            return redirect('wiki:moderation_queue')

        elif action == 'send_to_editor':
            # 📝 ОТПРАВИТЬ РЕДАКТОРУ - передаем редактору
            article.status = 'editor_review'
            article.moderated_by = request.user
            article.moderated_at = timezone.now()
            article.moderation_notes = moderation_notes
            article.save()

            messages.success(request, f'Статья "{article.title}" отправлена редактору на доработку.')
            return redirect('wiki:moderation_queue')

        elif action == 'reject':
            # 🚫 ОТКЛОНИТЬ ОКОНЧАТЕЛЬНО
            article.status = 'rejected'
            article.moderated_by = request.user
            article.moderated_at = timezone.now()
            article.moderation_notes = moderation_notes
            article.save()

            send_moderation_notification(article, 'rejected')
            messages.success(request, f'Статья "{article.title}" отклонена.')
            return redirect('wiki:moderation_queue')

    # Получаем существующие комментарии модерации
    moderation_comments = article.moderation_comments.all().order_by('-created_at')

    context = {
        'article': article,
        'moderation_comments': moderation_comments,
    }
    return render(request, 'wiki/article_moderate_enhanced.html', context)


@login_required
def resolve_moderation_comment(request, comment_id):
    """Помечает комментарий модерации как исправленный"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        comment = get_object_or_404(ModerationComment, id=comment_id)

        if not comment.article.can_moderate(request.user):
            return JsonResponse({'success': False, 'error': 'Нет прав для модерации'})

        comment.mark_as_resolved(request.user)
        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': 'Неверный запрос'})


@login_required
def delete_moderation_comment(request, comment_id):
    """Удаляет комментарий модерации"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        comment = get_object_or_404(ModerationComment, id=comment_id)

        if not comment.article.can_moderate(request.user):
            return JsonResponse({'success': False, 'error': 'Нет прав для модерации'})

        comment.delete()
        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': 'Неверный запрос'})


@login_required
def article_delete(request, slug):
    """Удаление статьи"""
    article = get_object_or_404(Article, slug=slug)

    if not article.can_delete(request.user):
        return JsonResponse({'success': False, 'error': 'У вас нет прав для удаления этой статьи'})

    if request.method == 'POST':
        try:
            article_title = article.title
            ActionLogger.log_action(
                request=request,
                action_type='article_delete',
                description=f'Пользователь {request.user.username} удалил статью "{article_title}"',
                target_object=article,
                extra_data={
                    'article_title': article_title,
                    'article_slug': article.slug,
                    'author': article.author.username,
                    'status': article.status,
                }
            )
            # Удаляем связанные медиафайлы
            for media in article.media_files.all():
                media_file_path = media.file.path
                media.delete()
                # Удаляем физический файл
                if os.path.exists(media_file_path):
                    os.remove(media_file_path)

            article.delete()

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Статья "{article_title}" удалена',
                    'redirect_url': reverse('wiki:my_articles')
                })
            else:
                messages.success(request, f'Статья "{article_title}" удалена')
                return redirect('wiki:my_articles')

        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(e)})
            else:
                messages.error(request, f'Ошибка при удалении статьи: {str(e)}')
                return redirect('wiki:article_detail', slug=slug)

    return JsonResponse({'success': False, 'error': 'Неверный метод запроса'})


def register_start(request):
    """Начало регистрации - ввод email"""
    if request.method == 'POST':
        form = EmailVerificationForm(request.POST)
        if form.is_valid():
            try:
                verification = form.send_verification_code('registration')
                request.session['registration_email'] = form.cleaned_data['email']
                messages.success(request, '📧 Код подтверждения отправлен на вашу почту!')
                return redirect('wiki:register_verify')
            except Exception as e:
                messages.error(request, f'❌ Ошибка отправки email: {str(e)}')
    else:
        form = EmailVerificationForm()

    context = {
        'form': form,
        'step': 1
    }
    return render(request, 'accounts/register_start.html', context)


def register_verify(request):
    """Ввод кода подтверждения"""
    email = request.session.get('registration_email')
    if not email:
        messages.error(request, '❌ Сначала укажите email')
        return redirect('wiki:register_start')

    if request.method == 'POST':
        form = CodeVerificationForm(request.POST, email=email, purpose='registration')
        if form.is_valid():
            verification = form.verification
            verification.is_used = True
            verification.save()
            request.session['verified_email'] = email
            request.session['verification_code'] = verification.code
            messages.success(request, '✅ Email подтвержден!')
            return redirect('wiki:register_complete')
    else:
        form = CodeVerificationForm(email=email, purpose='registration')

    context = {
        'form': form,
        'email': email,
        'step': 2
    }
    return render(request, 'accounts/register_verify.html', context)


def register_complete(request):
    """Завершение регистрации - ввод username и пароля"""
    email = request.session.get('verified_email')
    code = request.session.get('verification_code')

    if not email or not code:
        messages.error(request, '❌ Сначала подтвердите email')
        return redirect('wiki:register_start')

    if request.method == 'POST':
        form = CompleteRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = email
            user.is_active = True
            user.save()

            # Создаем профиль
            UserProfile.objects.get_or_create(user=user)

            # Очищаем сессию
            request.session.pop('registration_email', None)
            request.session.pop('verified_email', None)
            request.session.pop('verification_code', None)

            login(request, user)
            messages.success(request, f'✅ Регистрация завершена! Добро пожаловать, {user.username}!')
            return redirect('wiki:home')
    else:
        form = CompleteRegistrationForm(initial={'email': email, 'code': code})

    context = {
        'form': form,
        'step': 3
    }
    return render(request, 'accounts/register_complete.html', context)


def password_reset_request(request):
    """Запрос на восстановление пароля"""
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            try:
                email = form.cleaned_data['email']

                # Деактивируем старые коды для этого email
                EmailVerification.objects.filter(email=email, purpose='password_reset').update(is_used=True)

                # Создаем новый код
                verification = EmailVerification.objects.create(
                    email=email,
                    purpose='password_reset'
                )

                # Отправляем email
                subject = 'Код восстановления пароля'
                message = f'''
                Ваш код восстановления пароля: {verification.code}

                Код действителен в течение 15 минут.

                Если вы не запрашивали восстановление пароля, проигнорируйте это сообщение.
                '''

                try:
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [email],
                        fail_silently=False,
                    )

                    request.session['reset_email'] = email
                    messages.success(request, '📧 Код восстановления отправлен на вашу почту!')
                    return redirect('wiki:password_reset_verify')

                except Exception as e:
                    messages.error(request, f'❌ Ошибка отправки email: {str(e)}')
                    # Очищаем созданный код если отправка не удалась
                    verification.delete()

            except Exception as e:
                messages.error(request, f'❌ Ошибка: {str(e)}')
        else:
            # Показываем ошибки формы
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'❌ {error}')
    else:
        form = PasswordResetRequestForm()

    context = {
        'form': form
    }
    return render(request, 'accounts/password_reset_request.html', context)


def password_reset_verify(request):
    """Подтверждение кода для восстановления пароля"""
    email = request.session.get('reset_email')
    if not email:
        messages.error(request, '❌ Сначала укажите email')
        return redirect('wiki:password_reset_request')

    if request.method == 'POST':
        form = CodeVerificationForm(request.POST, email=email, purpose='password_reset')
        if form.is_valid():
            verification = form.verification
            verification.is_used = True
            verification.save()
            request.session['verified_reset_email'] = email
            request.session['reset_code'] = verification.code
            messages.success(request, '✅ Код подтвержден!')
            return redirect('wiki:password_reset_complete')
        else:
            # Показываем ошибки формы
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'❌ {error}')
    else:
        form = CodeVerificationForm(email=email, purpose='password_reset')

    context = {
        'form': form,
        'email': email
    }
    return render(request, 'accounts/password_reset_verify.html', context)


def password_reset_complete(request):
    """Установка нового пароля"""
    email = request.session.get('verified_reset_email')
    code = request.session.get('reset_code')

    if not email or not code:
        messages.error(request, '❌ Сначала подтвердите email')
        return redirect('wiki:password_reset_request')

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        messages.error(request, '❌ Пользователь не найден')
        return redirect('wiki:password_reset_request')

    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['new_password1']
            user.set_password(new_password)
            user.save()

            # Очищаем сессию
            request.session.pop('reset_email', None)
            request.session.pop('verified_reset_email', None)
            request.session.pop('reset_code', None)

            messages.success(request, '✅ Пароль успешно изменен! Теперь вы можете войти.')
            return redirect('wiki:login')
    else:
        form = PasswordResetForm(initial={'code': code})

    context = {
        'form': form,
        'email': email
    }
    return render(request, 'accounts/password_reset_complete.html', context)


# wiki/views.py - добавьте эти функции

def telegram_auth(request):
    """Страница авторизации через Telegram Web App"""
    return render(request, 'wiki/telegram_auth.html', {
        'telegram_bot_username': getattr(settings, 'TELEGRAM_BOT_USERNAME', ''),
    })


def telegram_callback(request):
    """Обработка callback от Telegram Web App"""
    if request.method == 'POST':
        try:
            init_data = request.POST.get('initData', '')

            if not init_data:
                return JsonResponse({'success': False, 'error': 'Не удалось получить данные от Telegram'})

            # Здесь будет логика проверки данных Telegram
            # Пока имитируем успешную авторизацию
            return JsonResponse({'success': True, 'message': 'Авторизация успешна'})

        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Ошибка авторизации: {str(e)}'})

    return JsonResponse({'success': False, 'error': 'Неверный метод запроса'})


@login_required
def telegram_disconnect(request):
    """Отвязка Telegram аккаунта"""
    if not request.user.is_authenticated:
        messages.error(request, '❌ Сначала войдите в аккаунт')
        return redirect('wiki:login')

    try:
        telegram_user = TelegramUser.objects.get(user=request.user)
        telegram_user.delete()
        messages.success(request, '✅ Telegram аккаунт отвязан')
    except TelegramUser.DoesNotExist:
        messages.error(request, '❌ Telegram аккаунт не привязан')

    return redirect('wiki:profile')


@login_required
def telegram_auth_code(request):
    """Страница для ввода кода авторизации Telegram"""
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()

        if not code:
            messages.error(request, '❌ Введите код авторизации')
            return redirect('wiki:telegram_auth_code')

        if len(code) != 6 or not code.isdigit():
            messages.error(request, '❌ Код должен состоять из 6 цифр')
            return redirect('wiki:telegram_auth_code')

        # Проверяем код и привязываем аккаунт
        success, message = TelegramAuthManager.verify_auth_code(code, request.user)

        if success:
            messages.success(request, f'✅ {message}')
            return redirect('wiki:profile')
        else:
            messages.error(request, f'❌ {message}')
            return redirect('wiki:telegram_auth_code')

    # Показываем активные коды (для отладки)
    active_codes = TelegramAuthManager.get_pending_codes()

    return render(request, 'wiki/telegram_auth_code.html', {
        'active_codes': active_codes
    })


@login_required
def telegram_generate_test_code(request):
    """Генерирует тестовый код авторизации"""
    if request.method == 'POST':
        # Тестовые данные Telegram пользователя
        test_telegram_data = {
            'id': 123456789,  # Тестовый ID
            'username': 'test_user',
            'first_name': 'Test',
            'last_name': 'User'
        }

        code = TelegramAuthManager.generate_auth_code(test_telegram_data)

        messages.success(request, f'✅ Тестовый код создан: {code}')
        messages.info(request, '💡 Используйте этот код на странице ввода кода')

        return redirect('wiki:telegram_auth_code')

    return redirect('wiki:telegram_auth_code')


@login_required
def telegram_link_with_code(request):
    """Привязка Telegram аккаунта через код (альтернативный endpoint)"""
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()

        if not code:
            messages.error(request, '❌ Введите код авторизации')
            return redirect('wiki:profile')

        success, message = TelegramAuthManager.verify_auth_code(code, request.user)

        if success:
            messages.success(request, f'✅ {message}')
        else:
            messages.error(request, f'❌ {message}')

        return redirect('wiki:profile')

    return redirect('wiki:profile')


# В views.py ДОБАВИТЬ новые функции:

def telegram_webapp_login(request):
    """Страница входа через Telegram Web App"""
    if request.user.is_authenticated:
        return redirect('wiki:home')

    return render(request, 'wiki/telegram_webapp_login.html', {
        'telegram_bot_username': getattr(settings, 'TELEGRAM_BOT_USERNAME', ''),
    })


def telegram_webapp_callback(request):
    """Обработка callback от Telegram Web App для входа"""
    if request.method == 'POST':
        try:
            init_data = request.POST.get('initData', '')

            if not init_data:
                return JsonResponse({'success': False, 'error': 'Не удалось получить данные от Telegram'})

            # Проверяем данные Telegram
            telegram_auth = TelegramAuth(settings.TELEGRAM_BOT_TOKEN)
            is_valid, user_data = telegram_auth.verify_telegram_webapp_data(init_data)

            if not is_valid:
                return JsonResponse({'success': False, 'error': 'Неверные данные авторизации'})

            # Аутентифицируем пользователя
            user, is_new = telegram_auth.authenticate_user(request, user_data)

            if user:
                response_data = {
                    'success': True,
                    'is_new': is_new,
                    'username': user.username,
                    'redirect_url': reverse('wiki:home')
                }

                if is_new:
                    response_data['message'] = f'Добро пожаловать, {user.username}! Аккаунт создан автоматически.'
                else:
                    response_data['message'] = f'С возвращением, {user.username}!'

                return JsonResponse(response_data)
            else:
                return JsonResponse({'success': False, 'error': 'Ошибка аутентификации'})

        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Ошибка авторизации: {str(e)}'})

    return JsonResponse({'success': False, 'error': 'Неверный метод запроса'})


# В views.py ЗАМЕНИТЬ функцию telegram_quick_login:

def telegram_quick_login(request):
    """Простой быстрый вход через Telegram"""
    if request.user.is_authenticated:
        return redirect('wiki:home')

    # Получаем параметры из URL
    telegram_id = request.GET.get('tg_id')
    username = request.GET.get('username')

    if telegram_id:
        try:
            # Ищем пользователя по telegram_id
            telegram_user = TelegramUser.objects.get(telegram_id=telegram_id)
            user = telegram_user.user

            # Логиним пользователя
            auth_login(request, user)

            messages.success(request, f'✅ Добро пожаловать, {user.username}!')

            # Перенаправляем на главную
            return redirect('wiki:home')

        except TelegramUser.DoesNotExist:
            messages.error(request,
                           '❌ Аккаунт не привязан. Сначала привяжите Telegram аккаунт через команду /auth в боте.')
        except Exception as e:
            messages.error(request, f'❌ Ошибка входа: {str(e)}')

    # Показываем инструкцию
    return render(request, 'wiki/telegram_quick_login.html', {
        'telegram_bot_username': getattr(settings, 'TELEGRAM_BOT_USERNAME', ''),
    })


@login_required
def group_permissions_info(request):
    """Страница с информацией о правах групп"""
    if not request.user.is_staff:
        return render(request, 'wiki/access_denied.html', {
            'message': 'Только администраторы могут просматривать эту страницу.'
        })

    context = {
        'group_permissions': GROUP_PERMISSIONS,
    }
    return render(request, 'wiki/group_permissions_info.html', context)


@login_required
def article_resubmit(request, slug):
    """Отправка статьи на повторную модерацию"""
    article = get_object_or_404(Article, slug=slug)

    # ПРАВИЛЬНАЯ проверка с передачей пользователя
    if not article.can_be_resubmitted(request.user):
        messages.error(request, '❌ Вы не можете отправить эту статью на модерацию.')
        return redirect('wiki:article_detail', slug=slug)

    if request.method == 'POST':
        if article.resubmit_for_moderation():
            messages.success(request, '✅ Статья отправлена на модерацию! Ожидайте проверки.')
        else:
            messages.error(request, '❌ Не удалось отправить статью на модерацию. Проверьте статус статьи.')

    return redirect('wiki:article_detail', slug=slug)


@login_required
def article_delete_by_author(request, slug):
    """Удаление статьи автором"""
    article = get_object_or_404(Article, slug=slug)

    # ПРАВИЛЬНАЯ проверка с передачей пользователя
    if not article.can_be_deleted_by_author(request.user):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'У вас нет прав для удаления этой статьи или статья не может быть удалена в текущем статусе'
            })
        messages.error(request, '❌ Вы не можете удалить эту статью.')
        return redirect('wiki:article_detail', slug=slug)

    if request.method == 'POST':
        try:
            article_title = article.title
            article.delete()

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Статья "{article_title}" удалена',
                    'redirect_url': reverse('wiki:my_articles')
                })
            else:
                messages.success(request, f'✅ Статья "{article_title}" удалена')
                return redirect('wiki:my_articles')

        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(e)})
            else:
                messages.error(request, f'❌ Ошибка при удалении статьи: {str(e)}')
                return redirect('wiki:article_detail', slug=slug)

    return render(request, 'wiki/confirm_article_delete.html', {'article': article})


@login_required
def send_to_editor(request, slug):
    """Отправка статьи редактору на доработку"""
    article = get_object_or_404(Article, slug=slug)

    if not (request.user.is_staff or request.user.groups.filter(name__in=['Модератор', 'Администратор']).exists()):
        return JsonResponse({'success': False, 'error': 'Нет прав для модерации'})

    if request.method == 'POST':
        article.status = 'editor_review'
        article.moderated_by = request.user
        article.moderated_at = timezone.now()
        article.save()

        messages.success(request, f'Статья "{article.title}" отправлена редактору на доработку.')
        return redirect('wiki:moderation_queue')

    return redirect('wiki:article_moderate_enhanced', slug=slug)


@login_required
def article_return_to_draft(request, slug):
    """Возвращает статью в черновики из статуса 'требует правок'"""
    article = get_object_or_404(Article, slug=slug)

    # Проверяем, что пользователь - автор и статья в правильном статусе
    if request.user != article.author or article.status != 'needs_correction':
        messages.error(request, '❌ Вы не можете вернуть эту статью в черновики.')
        return redirect('wiki:article_detail', slug=slug)

    if request.method == 'POST':
        article.status = 'draft'
        article.save()
        messages.success(request, '✅ Статья возвращена в черновики для редактирования.')

    return redirect('wiki:article_detail', slug=slug)


@staff_member_required
def action_logs_view(request):
    """Страница просмотра логов действий (альтернатива админке)"""
    logs = ActionLog.objects.all().select_related('user').order_by('-created_at')

    # Фильтрация
    action_type = request.GET.get('action_type')
    user_id = request.GET.get('user')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if action_type:
        logs = logs.filter(action_type=action_type)
    if user_id:
        logs = logs.filter(user_id=user_id)
    if date_from:
        logs = logs.filter(created_at__gte=date_from)
    if date_to:
        logs = logs.filter(created_at__lte=date_to)

    # Пагинация
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Статистика
    total_logs = logs.count()
    users = User.objects.filter(actionlog__isnull=False).distinct()
    action_types = ActionLog.ACTION_TYPES

    context = {
        'page_obj': page_obj,
        'total_logs': total_logs,
        'users': users,
        'action_types': action_types,
        'filters': {
            'action_type': action_type,
            'user_id': user_id,
            'date_from': date_from,
            'date_to': date_to,
        }
    }

    return render(request, 'wiki/action_logs.html', context)


@staff_member_required
def export_logs_json(request):
    """Экспорт логов в JSON"""
    logs = ActionLog.objects.all().select_related('user').order_by('-created_at')

    # Применяем фильтры как в основном view
    action_type = request.GET.get('action_type')
    user_id = request.GET.get('user')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if action_type:
        logs = logs.filter(action_type=action_type)
    if user_id:
        logs = logs.filter(user_id=user_id)
    if date_from:
        logs = logs.filter(created_at__gte=date_from)
    if date_to:
        logs = logs.filter(created_at__lte=date_to)

    logs_data = []
    for log in logs:
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
    response['Content-Disposition'] = 'attachment; filename="action_logs_export.json"'
    return response


@login_required
def debug_create_log(request):
    """Создание тестовой записи в логах для отладки"""
    ActionLogger.log_action(
        request=request,
        action_type='system',
        description=f'Тестовый лог от пользователя {request.user.username}'
    )

    messages.success(request, '✅ Тестовая запись в логах создана!')
    return redirect('wiki:home')


@login_required
def debug_test_logs(request):
    """Страница для тестирования логирования"""
    if request.method == 'POST':
        action_type = request.POST.get('action_type', 'system')
        description = request.POST.get('description', 'Тестовое описание')

        ActionLogger.log_action(
            request=request,
            action_type=action_type,
            description=description,
            extra_data={
                'test_data': 'Это тестовые данные',
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            }
        )

        messages.success(request, f'✅ Тестовый лог создан: {action_type}')
        return redirect('wiki:debug_test_logs')

    # Показываем последние логи
    recent_logs = ActionLog.objects.all().order_by('-created_at')[:10]

    return render(request, 'wiki/debug_test_logs.html', {
        'recent_logs': recent_logs,
        'action_types': ActionLog.ACTION_TYPES,
    })


@login_required
def mark_tutorial_seen(request, tutorial_type):
    """Отмечает подсказку как просмотренную"""
    from .models import UserTutorial

    tutorial, created = UserTutorial.objects.get_or_create(user=request.user)

    # Проверяем валидность типа подсказки
    valid_types = ['welcome', 'article_create', 'search', 'profile', 'messages', 'categories']
    if tutorial_type in valid_types:
        setattr(tutorial, f'has_seen_{tutorial_type}', True)
        tutorial.save()

        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': 'Invalid tutorial type'})


@login_required
def disable_tutorials(request):
    """Отключает все подсказки"""
    from .models import UserTutorial

    tutorial, created = UserTutorial.objects.get_or_create(user=request.user)
    tutorial.tutorials_disabled = True
    tutorial.save()

    messages.success(request, 'Подсказки отключены')
    return redirect(request.META.get('HTTP_REFERER', 'wiki:home'))


@login_required
def reset_tutorials(request):
    """Сбрасывает все подсказки"""
    from .models import UserTutorial

    tutorial, created = UserTutorial.objects.get_or_create(user=request.user)
    tutorial.has_seen_welcome = False
    tutorial.has_seen_article_create = False
    tutorial.has_seen_search = False
    tutorial.has_seen_profile = False
    tutorial.has_seen_messages = False
    tutorial.has_seen_categories = False
    tutorial.tutorials_disabled = False
    tutorial.save()

    messages.success(request, 'Подсказки сброшены')
    return redirect(request.META.get('HTTP_REFERER', 'wiki:home'))


def wrap_text(text, max_line_length):
    """Разбивает текст на строки заданной длины"""
    if not text:
        return []

    words = text.split()
    lines = []
    current_line = []

    for word in words:
        # Проверяем длину текущей строки с новым словом
        test_line = ' '.join(current_line + [word])
        if len(test_line) <= max_line_length:
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


def clean_html_for_pdf(html_content):
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
    }

    for entity, replacement in replacements.items():
        text_only = text_only.replace(entity, replacement)

    # Декодируем Unicode entities
    text_only = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text_only)
    text_only = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), text_only)

    # Удаляем лишние пробелы и переносы
    text_only = re.sub(r'\s+', ' ', text_only)
    text_only = re.sub(r'\n\s*\n', '\n\n', text_only)

    return text_only.strip()


@login_required
def export_article_pdf(request, slug):
    """Минималистичный экспорт статьи в PDF"""
    article = get_object_or_404(Article, slug=slug)

    if article.status != 'published' and not article.can_edit(request.user):
        return render(request, 'wiki/access_denied.html', {
            'message': 'У вас нет прав для экспорта этой статьи.'
        })

    try:
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
        import io

        # PDF с нормальными полями
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer,
                                pagesize=A4,
                                rightMargin=20 * mm,
                                leftMargin=20 * mm,
                                topMargin=25 * mm,
                                bottomMargin=20 * mm)

        # Регистрируем шрифты
        def register_custom_fonts():
            try:
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
                import os
                from django.conf import settings

                font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'DejaVuSans.ttf')

                if os.path.exists(font_path):
                    pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
                    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', font_path))
                    return True
            except:
                pass
            return False

        fonts_registered = register_custom_fonts()
        font_normal = 'DejaVuSans' if fonts_registered else 'Helvetica'
        font_bold = 'DejaVuSans-Bold' if fonts_registered else 'Helvetica-Bold'

        # Стили
        styles = getSampleStyleSheet()

        # 1. Заголовок статьи
        title_style = ParagraphStyle(
            'ArticleTitle',
            parent=styles['Heading1'],
            fontName=font_bold,
            fontSize=18,
            leading=22,
            spaceAfter=8 * mm,
            textColor=colors.HexColor('#1a365d'),
            alignment=TA_CENTER
        )

        # 2. Мета информация
        meta_style = ParagraphStyle(
            'MetaInfo',
            parent=styles['Normal'],
            fontName=font_normal,
            fontSize=9,
            leading=11,
            spaceAfter=1 * mm,
            textColor=colors.HexColor('#4a5568'),
            alignment=TA_CENTER
        )

        # 3. Статус (простой, без огромного блока)
        def get_status_style(status):
            colors_map = {
                'published': ('#10b981', '#065f46'),  # зеленый
                'draft': ('#6b7280', '#374151'),  # серый
                'review': ('#f59e0b', '#92400e'),  # желтый
                'needs_correction': ('#ef4444', '#991b1b'),  # красный
                'editor_review': ('#3b82f6', '#1e40af'),  # синий
                'author_review': ('#8b5cf6', '#5b21b6'),  # фиолетовый
                'rejected': ('#dc2626', '#7f1d1d'),  # темно-красный
                'archived': ('#9ca3af', '#4b5563'),  # серый
            }
            bg_color, text_color = colors_map.get(status, ('#6b7280', '#374151'))

            return ParagraphStyle(
                f'Status_{status}',
                parent=styles['Normal'],
                fontName=font_bold,
                fontSize=10,
                leading=12,
                spaceAfter=6 * mm,
                textColor=colors.HexColor(text_color),
                alignment=TA_CENTER,
                borderWidth=1,
                borderColor=colors.HexColor(bg_color),
                borderRadius=4,
                borderPadding=(6, 12, 6, 12)
            )

        # 4. Основной текст
        body_style = ParagraphStyle(
            'ArticleBody',
            parent=styles['Normal'],
            fontName=font_normal,
            fontSize=11,
            leading=15,
            spaceAfter=4 * mm,
            textColor=colors.HexColor('#2d3748'),
            alignment=TA_JUSTIFY,
            firstLineIndent=20
        )

        # 5. Разделитель
        divider_style = ParagraphStyle(
            'Divider',
            parent=styles['Normal'],
            fontSize=1,
            spaceBefore=10 * mm,
            spaceAfter=10 * mm,
            borderWidth=0.5,
            borderColor=colors.HexColor('#e2e8f0')
        )

        # 6. Футер
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontName=font_normal,
            fontSize=8,
            leading=10,
            spaceBefore=15 * mm,
            textColor=colors.HexColor('#718096'),
            alignment=TA_CENTER
        )

        # Собираем контент
        story = []

        # 1. Заголовок
        story.append(Paragraph(article.title, title_style))

        # 2. Мета информация в таблице
        meta_table_data = [
            [Paragraph(f"<b>Автор:</b> {article.author.username}", meta_style)],
            [Paragraph(f"<b>Дата:</b> {article.created_at.strftime('%d.%m.%Y %H:%M')}", meta_style)],
        ]

        if article.published_at:
            meta_table_data.append(
                [Paragraph(f"<b>Опубликовано:</b> {article.published_at.strftime('%d.%m.%Y %H:%M')}", meta_style)]
            )

        meta_table = Table(meta_table_data, colWidths=[150 * mm])
        meta_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))

        story.append(meta_table)
        story.append(Spacer(1, 4 * mm))

        # 3. Статус (компактный)
        story.append(Paragraph(article.get_status_display(), get_status_style(article.status)))
        story.append(Spacer(1, 8 * mm))

        # 4. Категории и теги (если есть)
        if article.categories.exists() or article.tags.exists():
            info_lines = []

            if article.categories.exists():
                cats = ", ".join([cat.name for cat in article.categories.all()])
                if len(cats) > 60:
                    cats = cats[:57] + "..."
                info_lines.append(f"<b>Категории:</b> {cats}")

            if article.tags.exists():
                tags = ", ".join([tag.name for tag in article.tags.all()])
                if len(tags) > 60:
                    tags = tags[:57] + "..."
                info_lines.append(f"<b>Теги:</b> {tags}")

            for line in info_lines:
                story.append(Paragraph(line, meta_style))
                story.append(Spacer(1, 1 * mm))

            story.append(Spacer(1, 6 * mm))

        # 5. Краткое описание (если есть)
        if article.excerpt:
            excerpt_style = ParagraphStyle(
                'Excerpt',
                parent=body_style,
                fontStyle='italic',
                textColor=colors.HexColor('#4a5568'),
                alignment=TA_CENTER,
                leftIndent=0,
                rightIndent=0,
                spaceBefore=4 * mm,
                spaceAfter=8 * mm
            )
            clean_excerpt = clean_html_for_pdf(article.excerpt, 300)
            story.append(Paragraph(f'"{clean_excerpt}"', excerpt_style))

        # 6. Разделитель перед контентом
        story.append(Paragraph("", divider_style))

        # 7. Основной контент
        clean_content = clean_html_for_pdf(article.content)
        paragraphs = clean_content.split('\n')

        for i, para in enumerate(paragraphs):
            if para.strip():
                if i == 0:  # Первый абзац без отступа
                    first_style = ParagraphStyle('FirstPara', parent=body_style, firstLineIndent=0)
                    story.append(Paragraph(para.strip(), first_style))
                else:
                    story.append(Paragraph(para.strip(), body_style))
                story.append(Spacer(1, 3 * mm))

        # 8. Статистика (простая)
        story.append(Spacer(1, 10 * mm))
        stats_text = f"Просмотры: {article.views_count} • Лайки: {article.get_likes_count()} • Комментарии: {article.comments.count()}"
        story.append(Paragraph(stats_text, ParagraphStyle(
            'Stats', parent=meta_style, fontSize=9, alignment=TA_CENTER
        )))

        # 9. Футер
        story.append(Spacer(1, 15 * mm))

        footer_lines = [
            f"Экспортировано: {timezone.now().strftime('%d.%m.%Y %H:%M')}",
            "Форум ВЕДЬМАК",
            f"© {timezone.now().strftime('%Y')} Все права защищены"
        ]

        for line in footer_lines:
            story.append(Paragraph(line, footer_style))

        # Создаем PDF
        doc.build(story)

        # Response
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        filename = f"{article.slug}_{timezone.now().strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        # Логирование
        ActionLogger.log_action(
            request=request,
            action_type='article_export',
            description=f'Пользователь {request.user.username} экспортировал статью "{article.title}"',
            target_object=article
        )

        return response

    except Exception as e:
        import traceback
        print(f"Ошибка при создании PDF: {str(e)}")
        print(traceback.format_exc())

        messages.error(request, f'Ошибка при создании PDF: {str(e)}')
        return redirect('wiki:article_detail', slug=slug)


@login_required
def export_articles_list(request):
    """Экспорт списка статей в PDF"""

    # Определяем какие статьи экспортировать
    if request.user.is_staff or request.user.groups.filter(name__in=['Модератор', 'Администратор']).exists():
        # Админы/модераторы - все статьи
        articles = Article.objects.all()
        title = "ВСЕ СТАТЬИ ФОРУМА ВЕДЬМАК"
    else:
        # Обычные пользователи - только свои статьи
        articles = Article.objects.filter(author=request.user)
        title = f"МОИ СТАТЬИ ({request.user.username})"

    # Применяем фильтры
    status_filter = request.GET.get('status')
    category_filter = request.GET.get('category')

    if status_filter:
        articles = articles.filter(status=status_filter)
    if category_filter:
        articles = articles.filter(categories__slug=category_filter)

    articles = articles.order_by('-created_at')

    try:
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.units import mm, inch
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from io import BytesIO
        import os
        from django.conf import settings

        buffer = BytesIO()

        # Используем горизонтальную ориентацию (ландшафт) для лучшего размещения колонок
        doc = SimpleDocTemplate(
            buffer,
            pagesize=(11 * inch, 8.5 * inch),  # Ландшафтный A4
            rightMargin=10 * mm,
            leftMargin=10 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm
        )

        # Регистрируем кириллические шрифты
        def register_cyrillic_fonts():
            """Регистрация кириллических шрифтов"""
            try:
                # Пути к шрифтам
                font_dir = os.path.join(settings.BASE_DIR, 'static', 'fonts')

                # Используем DejaVuSans если есть
                dejavu_path = os.path.join(font_dir, 'DejaVuSans.ttf')
                dejavu_bold_path = os.path.join(font_dir, 'DejaVuSans-Bold.ttf')

                if os.path.exists(dejavu_path) and os.path.exists(dejavu_bold_path):
                    # Регистрируем DejaVuSans
                    pdfmetrics.registerFont(TTFont('DejaVuSans', dejavu_path))
                    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', dejavu_bold_path))
                    return 'DejaVuSans', 'DejaVuSans-Bold'

                # Или используем Arial если есть
                arial_path = os.path.join(font_dir, 'arial.ttf')
                arial_bold_path = os.path.join(font_dir, 'arialbd.ttf')

                if os.path.exists(arial_path) and os.path.exists(arial_bold_path):
                    pdfmetrics.registerFont(TTFont('Arial', arial_path))
                    pdfmetrics.registerFont(TTFont('Arial-Bold', arial_bold_path))
                    return 'Arial', 'Arial-Bold'

                # Пробуем найти системные шрифты
                import platform
                system = platform.system()

                if system == 'Windows':
                    # Windows пути
                    fonts_path = os.environ.get('WINDIR', '') + '\\Fonts\\'
                    if os.path.exists(fonts_path + 'arial.ttf'):
                        pdfmetrics.registerFont(TTFont('Arial', fonts_path + 'arial.ttf'))
                        pdfmetrics.registerFont(TTFont('Arial-Bold', fonts_path + 'arialbd.ttf'))
                        return 'Arial', 'Arial-Bold'

                elif system == 'Linux':
                    # Linux пути
                    linux_fonts = [
                        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
                        '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf'
                    ]
                    for font_path in linux_fonts:
                        if os.path.exists(font_path):
                            pdfmetrics.registerFont(TTFont('Arial', font_path))
                            return 'Arial', 'Helvetica-Bold'

            except Exception as e:
                print(f"Ошибка регистрации шрифтов: {e}")

            # Fallback на стандартные шрифты
            return 'Helvetica', 'Helvetica-Bold'

        # Получаем названия шрифтов
        font_normal, font_bold = register_cyrillic_fonts()
        print(f"Используем шрифты: Normal={font_normal}, Bold={font_bold}")

        # Стили
        styles = getSampleStyleSheet()

        # Цвета для статусов
        status_colors = {
            'published': '#10b981',  # зеленый
            'draft': '#6b7280',  # серый
            'review': '#f59e0b',  # желтый
            'needs_correction': '#ef4444',  # красный
            'editor_review': '#3b82f6',  # синий
            'author_review': '#8b5cf6',  # фиолетовый
            'rejected': '#dc2626',  # темно-красный
            'archived': '#9ca3af',  # серый
        }

        # Создаем кастомные стили
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontName=font_bold,
            fontSize=16,
            leading=20,
            spaceAfter=6 * mm,
            textColor=colors.HexColor('#1e40af'),
            alignment=TA_CENTER
        )

        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=styles['Normal'],
            fontName=font_normal,
            fontSize=10,
            leading=12,
            spaceAfter=8 * mm,
            textColor=colors.HexColor('#6b7280'),
            alignment=TA_CENTER
        )

        header_style = ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontName=font_bold,
            fontSize=10,
            leading=12,
            textColor=colors.white,
            alignment=TA_CENTER,
            spaceBefore=2,
            spaceAfter=2
        )

        # Стиль для обычных ячеек
        cell_style = ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontName=font_normal,
            fontSize=9,
            leading=11,
            textColor=colors.HexColor('#374151'),
            alignment=TA_LEFT,
            wordWrap='CJK'  # Важно для переноса длинного текста
        )

        # Стиль для номеров и цифр
        number_style = ParagraphStyle(
            'NumberStyle',
            parent=cell_style,
            alignment=TA_CENTER,
            fontSize=8
        )

        # Собираем контент
        story = []

        # Заголовок отчета
        story.append(Paragraph(title, title_style))
        story.append(Paragraph(
            f"Дата формирования: {timezone.now().strftime('%d.%m.%Y в %H:%M')} | "
            f"Всего статей: {articles.count()}",
            subtitle_style
        ))

        # Подготовка данных для таблицы
        table_data = []

        # Заголовки таблицы с правильной шириной колонок
        headers = ['№', 'Название статьи', 'Статус', 'Автор', 'Дата', 'Просмотры']
        header_cells = [Paragraph(header, header_style) for header in headers]
        table_data.append(header_cells)

        # Добавляем статьи с нумерацией
        for idx, article in enumerate(articles[:50], 1):  # Ограничиваем 50 статей на страницу
            # Заголовок (обрезаем если длинный, добавляем переносы)
            title_text = article.title
            if len(title_text) > 80:
                title_text = title_text[:77] + "..."

            # Разбиваем длинные заголовки на строки
            title_lines = []
            words = title_text.split()
            current_line = ""
            for word in words:
                if len(current_line) + len(word) + 1 <= 40:
                    current_line += f"{word} "
                else:
                    if current_line:
                        title_lines.append(current_line.strip())
                    current_line = f"{word} "
            if current_line:
                title_lines.append(current_line.strip())

            title_para = Paragraph("<br/>".join(title_lines), cell_style) if len(title_lines) > 1 else Paragraph(
                title_text, cell_style)

            # Статус
            status_text = article.get_status_display()
            status_color = status_colors.get(article.status, '#6b7280')
            status_style = ParagraphStyle(
                f'StatusStyle_{article.status}',
                parent=cell_style,
                alignment=TA_CENTER,
                textColor=colors.white,
                backColor=colors.HexColor(status_color),
                fontSize=8,
                borderPadding=(2, 4, 2, 4),
                borderRadius=3
            )
            status_para = Paragraph(status_text, status_style)

            # Автор
            author_text = article.author.username if article.author else 'Аноним'
            if len(author_text) > 12:
                author_text = author_text[:10] + ".."
            author_para = Paragraph(author_text, ParagraphStyle(
                'AuthorStyle', parent=cell_style, alignment=TA_CENTER, fontSize=8
            ))

            # Дата
            date_text = article.created_at.strftime('%d.%m.%Y')
            date_para = Paragraph(date_text, ParagraphStyle(
                'DateStyle', parent=cell_style, alignment=TA_CENTER, fontSize=8
            ))

            # Просмотры
            views_text = str(article.views_count)
            views_para = Paragraph(views_text, ParagraphStyle(
                'ViewsStyle', parent=cell_style, alignment=TA_CENTER, fontSize=8
            ))

            row = [
                Paragraph(str(idx), number_style),  # №
                title_para,  # Название
                status_para,  # Статус
                author_para,  # Автор
                date_para,  # Дата
                views_para  # Просмотры
            ]
            table_data.append(row)

        # Создаем таблицу с ОПТИМАЛЬНЫМИ ШИРИНАМИ КОЛОНОК для ландшафтной ориентации
        # Общая ширина: 11 дюймов - 2*10mm = примерно 275mm
        # Распределяем:
        col_widths = [
            10 * mm,  # № (1 см)
            120 * mm,  # Название (12 см) - самая широкая колонка
            25 * mm,  # Статус (2.5 см)
            25 * mm,  # Автор (2.5 см)
            20 * mm,  # Дата (2 см)
            15 * mm  # Просмотры (1.5 см)
        ]  # Итого: ~173mm + отступы

        table = Table(table_data, colWidths=col_widths, repeatRows=1)

        # Применяем стили к таблице
        table.setStyle(TableStyle([
            # Заголовки
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), font_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),

            # Все строки данных
            ('FONTNAME', (0, 1), (-1, -1), font_normal),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),

            # Выравнивание колонок
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # № - по центру
            ('ALIGN', (2, 1), (2, -1), 'CENTER'),  # Статус - по центру
            ('ALIGN', (3, 1), (3, -1), 'CENTER'),  # Автор - по центру
            ('ALIGN', (4, 1), (4, -1), 'CENTER'),  # Дата - по центру
            ('ALIGN', (5, 1), (5, -1), 'CENTER'),  # Просмотры - по центру

            # Границы
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),

            # Чередование цвета строк
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [
                colors.HexColor('#ffffff'),  # Белый
                colors.HexColor('#f8fafc')  # Очень светло-голубой
            ]),

            # Отступы внутри ячеек
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))

        story.append(table)

        # Добавляем статистику в конце
        story.append(Spacer(1, 10 * mm))

        # Статистика по статусам
        status_stats = []
        for status_code, status_name in Article.STATUS_CHOICES:
            count = articles.filter(status=status_code).count()
            if count > 0:
                status_stats.append((status_name, count))

        if status_stats:
            # Заголовок статистики
            story.append(Paragraph(
                "<b>Статистика по статусам:</b>",
                ParagraphStyle(
                    'StatsTitle',
                    parent=styles['Normal'],
                    fontName=font_bold,
                    fontSize=10,
                    textColor=colors.HexColor('#1e40af'),
                    spaceAfter=3 * mm
                )
            ))

            # Таблица статистики
            stats_data = []
            for status_name, count in status_stats:
                stats_data.append([status_name, str(count)])

            stats_table = Table(stats_data, colWidths=[100 * mm, 30 * mm])
            stats_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), font_normal),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9fafb')),
                ('PADDING', (0, 0), (-1, -1), 4),
            ]))

            story.append(stats_table)

        # Итоговая строка
        story.append(Spacer(1, 8 * mm))
        total_text = f"<b>Итого:</b> {articles.count()} статей"
        story.append(Paragraph(
            total_text,
            ParagraphStyle(
                'TotalStats',
                parent=styles['Normal'],
                fontName=font_bold,
                fontSize=10,
                textColor=colors.HexColor('#1e40af'),
                alignment=TA_CENTER,
                spaceBefore=5 * mm,
                spaceAfter=5 * mm
            )
        ))

        # Футер
        story.append(Spacer(1, 10 * mm))
        footer_text = (
            f"Сформировано: {timezone.now().strftime('%d.%m.%Y %H:%M')} | "
            f"Пользователь: {request.user.username} | "
            f"Форум 'ВЕДЬМАК' © {timezone.now().strftime('%Y')}"
        )
        story.append(Paragraph(
            footer_text,
            ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontName=font_normal,
                fontSize=8,
                textColor=colors.HexColor('#6b7280'),
                alignment=TA_CENTER
            )
        ))

        # Строим PDF
        doc.build(story)

        # Подготавливаем response
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        filename = f"articles_export_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        # Кодируем имя файла для русских символов
        try:
            from urllib.parse import quote
            response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
        except:
            pass

        # Логируем действие
        ActionLogger.log_action(
            request=request,
            action_type='articles_export',
            description=f'Экспорт списка статей ({articles.count()} шт.)',
            extra_data={'count': articles.count(), 'format': 'pdf'}
        )

        return response

    except Exception as e:
        import traceback
        error_msg = f"Ошибка при создании PDF: {str(e)}"
        print(error_msg)
        traceback.print_exc()

        # Fallback в TXT
        response = HttpResponse(
            f"Ошибка при создании PDF: {str(e)}\n\n"
            f"Список статей ({articles.count()}):\n"
            + "\n".join([f"{i + 1}. {a.title} ({a.get_status_display()})" for i, a in enumerate(articles)]),
            content_type='text/plain; charset=utf-8'
        )
        response['Content-Disposition'] = 'attachment; filename="articles_backup.txt"'
        return response


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
        '&laquo;': '«',
        '&raquo;': '»',
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


class HelpView(TemplateView):
    """Простое представление для страницы помощи"""
    template_name = 'help/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Помощь и руководство пользователя'
        return context


class FAQView(TemplateView):
    """Часто задаваемые вопросы"""
    template_name = 'help/faq.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Статические FAQ данные
        context['faqs'] = [
            {
                'question': 'Как зарегистрироваться на форуме?',
                'answer': 'Нажмите кнопку "Регистрация" в правом верхнем углу, заполните форму и подтвердите email.'
            },
            {
                'question': 'Как создать статью?',
                'answer': 'После регистрации нажмите "Новая статья" в меню, заполните заголовок и содержание, выберите категорию.'
            },
            {
                'question': 'Как редактировать статью?',
                'answer': 'На странице своей статьи нажмите кнопку "Редактировать". Только автор может редактировать свои статьи.'
            },
            {
                'question': 'Как оставить комментарий?',
                'answer': 'Войдите в систему и внизу статьи введите текст комментария в поле и нажмите "Отправить".'
            },
            {
                'question': 'Как экспортировать статью в PDF?',
                'answer': 'На странице статьи нажмите кнопку "Экспорт в PDF" для загрузки статьи в формате PDF.'
            },
            {
                'question': 'Как искать статьи?',
                'answer': 'Используйте поиск в верхней части сайта или фильтры по категориям и тегам.'
            },
        ]
        return context


class StatisticsView(UserPassesTestMixin, TemplateView):
    """Представление для просмотра статистики"""
    template_name = 'wiki/statistics.html'

    def test_func(self):
        """Только для staff и модераторов"""
        return self.request.user.is_staff or self.request.user.groups.filter(
            name__in=['Модератор', 'Администратор']
        ).exists()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Получаем топовую статистику
        from django.db.models import Count, Sum, Max

        # Топ 3 самых просматриваемых статей
        top_viewed = Article.objects.filter(
            status='published'
        ).order_by('-views_count')[:3]

        # Топ 3 самых лайкнутых статей
        top_liked = Article.objects.filter(
            status='published'
        ).annotate(
            likes_count=Count('likes')
        ).order_by('-likes_count')[:3]

        # Топ 3 статей с комментариями
        top_commented = Article.objects.filter(
            status='published'
        ).annotate(
            comments_count=Count('comments')
        ).order_by('-comments_count')[:3]

        # Самые просматриваемые категории
        top_categories = Category.objects.filter(
            articles__status='published'
        ).annotate(
            total_views=Sum('articles__views_count'),
            article_count=Count('articles')
        ).filter(
            article_count__gt=0
        ).order_by('-total_views')[:5]

        # Популярные поисковые запросы
        popular_searches = SearchQuery.objects.values('query').annotate(
            count=Count('id'),
            last_search=Max('created_at')
        ).order_by('-count')[:10]

        # Общая статистика
        total_articles = Article.objects.filter(status='published').count()
        total_users = User.objects.filter(is_active=True).count()
        total_comments = Comment.objects.count()
        total_views = Article.objects.filter(status='published').aggregate(
            total=Sum('views_count')
        )['total'] or 0

        # Статистика за последние 7 дней
        seven_days_ago = timezone.now() - timezone.timedelta(days=7)
        recent_articles = Article.objects.filter(
            created_at__gte=seven_days_ago,
            status='published'
        ).count()

        recent_users = User.objects.filter(
            date_joined__gte=seven_days_ago
        ).count()

        context.update({
            'top_viewed': top_viewed,
            'top_liked': top_liked,
            'top_commented': top_commented,
            'top_categories': top_categories,
            'popular_searches': popular_searches,

            'total_articles': total_articles,
            'total_users': total_users,
            'total_comments': total_comments,
            'total_views': total_views,

            'recent_articles': recent_articles,
            'recent_users': recent_users,
        })

        return context

@csrf_exempt
@login_required
def update_stats_api(request):
    """API для обновления статистики"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Доступ запрещен'}, status=403)

    if request.method == 'POST':
        try:
            # Обновляем статистику для всех статей
            articles = Article.objects.filter(status='published')
            for article in articles:
                StatsCollector.update_article_stats(article.id)

            # Обновляем статистику категорий
            categories = Category.objects.all()
            for category in categories:
                StatsCollector.update_category_stats(category.id)

            # Обновляем дневную статистику
            StatsCollector.update_daily_stats()

            return JsonResponse({
                'success': True,
                'message': 'Статистика обновлена',
                'articles_updated': articles.count(),
                'categories_updated': categories.count(),
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    return JsonResponse({'error': 'Метод не поддерживается'}, status=405)


class ExportStatsView(UserPassesTestMixin, View):
    """Экспорт статистики в PDF"""

    def test_func(self):
        """Только для staff"""
        return self.request.user.is_staff

    def get(self, request):
        # Можно использовать существующую функцию экспорта
        # или создать отдельную для статистики
        from django.http import HttpResponse
        return HttpResponse("Экспорт статистики пока не реализован")

def article_list(request):
    """Список всех опубликованных статей"""
    articles = Article.objects.filter(status='published').order_by('-created_at')
    context = {'articles': articles}
    return render(request, 'wiki/article_list.html', context)


@login_required
def export_statistics_pdf(request):
    """Экспорт статистики в PDF (по аналогии с export_articles_list)"""
    if not request.user.is_staff:
        return HttpResponseForbidden("Доступ запрещен")

    try:
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.units import mm, inch
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from io import BytesIO
        import os
        from django.conf import settings

        # Получаем статистику
        from django.db.models import Count, Sum

        # Топ 3 самых просматриваемых статей
        top_viewed = Article.objects.filter(
            status='published'
        ).order_by('-views_count')[:3]

        # Топ 3 самых лайкнутых статей
        top_liked = Article.objects.filter(
            status='published'
        ).annotate(
            likes_count=Count('likes')
        ).order_by('-likes_count')[:3]

        # Топ 3 статей с комментариями
        top_commented = Article.objects.filter(
            status='published'
        ).annotate(
            comments_count=Count('comments')
        ).order_by('-comments_count')[:3]

        # Самые просматриваемые категории
        top_categories = Category.objects.filter(
            articles__status='published'
        ).annotate(
            total_views=Sum('articles__views_count'),
            article_count=Count('articles')
        ).filter(
            article_count__gt=0
        ).order_by('-total_views')[:5]

        # Популярные поисковые запросы
        popular_searches = SearchQuery.objects.values('query').annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        # Общая статистика
        total_articles = Article.objects.filter(status='published').count()
        total_users = User.objects.filter(is_active=True).count()
        total_comments = Comment.objects.count()
        total_views = Article.objects.filter(status='published').aggregate(
            total=Sum('views_count')
        )['total'] or 0

        # Статистика за последние 7 дней
        seven_days_ago = timezone.now() - timezone.timedelta(days=7)
        recent_articles = Article.objects.filter(
            created_at__gte=seven_days_ago,
            status='published'
        ).count()

        recent_users = User.objects.filter(
            date_joined__gte=seven_days_ago
        ).count()

        # Создаем PDF
        buffer = BytesIO()

        # Используем горизонтальную ориентацию
        doc = SimpleDocTemplate(
            buffer,
            pagesize=(11 * inch, 8.5 * inch),  # Ландшафтный A4
            rightMargin=10 * mm,
            leftMargin=10 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm
        )

        # Регистрируем кириллические шрифты
        def register_cyrillic_fonts():
            """Регистрация кириллических шрифтов"""
            try:
                # Пути к шрифтам - ИСПРАВЛЕННЫЙ ПУТЬ
                font_dir = os.path.join(settings.BASE_DIR, 'wiki', 'static', 'fonts')

                print(f"🔍 Ищем шрифты в: {font_dir}")
                print(f"📁 Существует ли папка: {os.path.exists(font_dir)}")

                if os.path.exists(font_dir):
                    files = os.listdir(font_dir)
                    print(f"📄 Файлы в папке: {files}")

                # Используем DejaVuSans если есть
                dejavu_path = os.path.join(font_dir, 'DejaVuSans.ttf')
                dejavu_bold_path = os.path.join(font_dir, 'DejaVuSans-Bold.ttf')

                if os.path.exists(dejavu_path) and os.path.exists(dejavu_bold_path):
                    # Регистрируем DejaVuSans
                    pdfmetrics.registerFont(TTFont('DejaVuSans', dejavu_path))
                    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', dejavu_bold_path))
                    print("✅ Шрифты DejaVuSans успешно зарегистрированы")
                    return 'DejaVuSans', 'DejaVuSans-Bold'

                # Или используем Arial если есть
                arial_path = os.path.join(font_dir, 'arial.ttf')
                arial_bold_path = os.path.join(font_dir, 'arialbd.ttf')

                if os.path.exists(arial_path) and os.path.exists(arial_bold_path):
                    pdfmetrics.registerFont(TTFont('Arial', arial_path))
                    pdfmetrics.registerFont(TTFont('Arial-Bold', arial_bold_path))
                    return 'Arial', 'Arial-Bold'

                # Пробуем найти системные шрифты
                import platform
                system = platform.system()

                if system == 'Windows':
                    # Windows пути
                    fonts_path = os.environ.get('WINDIR', '') + '\\Fonts\\'
                    if os.path.exists(fonts_path + 'arial.ttf'):
                        pdfmetrics.registerFont(TTFont('Arial', fonts_path + 'arial.ttf'))
                        pdfmetrics.registerFont(TTFont('Arial-Bold', fonts_path + 'arialbd.ttf'))
                        return 'Arial', 'Arial-Bold'

                elif system == 'Linux':
                    # Linux пути
                    linux_fonts = [
                        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
                        '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf'
                    ]
                    for font_path in linux_fonts:
                        if os.path.exists(font_path):
                            pdfmetrics.registerFont(TTFont('Arial', font_path))
                            return 'Arial', 'Helvetica-Bold'

            except Exception as e:
                print(f"Ошибка регистрации шрифтов: {e}")

            # Fallback на стандартные шрифты
            print("⚠️ Используем стандартные шрифты Helvetica")
            return 'Helvetica', 'Helvetica-Bold'

        # Получаем названия шрифтов
        font_normal, font_bold = register_cyrillic_fonts()
        print(f"Используем шрифты: Normal={font_normal}, Bold={font_bold}")

        # Стили
        styles = getSampleStyleSheet()

        # Цвета для разделов
        section_colors = {
            'general': '#D4AF37',  # золотой
            'top_viewed': '#3b82f6',  # синий
            'top_liked': '#22c55e',  # зеленый
            'top_commented': '#8b5cf6',  # фиолетовый
            'categories': '#f59e0b',  # оранжевый
            'searches': '#ef4444',  # красный
        }

        # Создаем кастомные стили
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontName=font_bold,
            fontSize=18,
            leading=22,
            spaceAfter=6 * mm,
            textColor=colors.HexColor('#D4AF37'),
            alignment=TA_CENTER
        )

        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=styles['Normal'],
            fontName=font_normal,
            fontSize=10,
            leading=12,
            spaceAfter=8 * mm,
            textColor=colors.HexColor('#6b7280'),
            alignment=TA_CENTER
        )

        header_style = ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontName=font_bold,
            fontSize=10,
            leading=12,
            textColor=colors.white,
            alignment=TA_CENTER,
            spaceBefore=2,
            spaceAfter=2
        )

        # Стиль для обычных ячеек
        cell_style = ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontName=font_normal,
            fontSize=9,
            leading=11,
            textColor=colors.HexColor('#374151'),
            alignment=TA_LEFT,
            wordWrap='CJK'
        )

        # Стиль для номеров и цифр
        number_style = ParagraphStyle(
            'NumberStyle',
            parent=cell_style,
            alignment=TA_CENTER,
            fontSize=8
        )

        # Собираем контент
        story = []

        # Заголовок отчета
        story.append(Paragraph("СТАТИСТИКА ФОРУМА 'ВЕДЬМАК'", title_style))
        story.append(Paragraph(
            f"Дата формирования: {timezone.now().strftime('%d.%m.%Y в %H:%M')} | "
            f"Сформировано пользователем: {request.user.username}",
            subtitle_style
        ))
        story.append(Spacer(1, 10 * mm))

        # 1. Общая статистика
        story.append(Paragraph(
            "📊 ОБЩАЯ СТАТИСТИКА",
            ParagraphStyle(
                'SectionTitle',
                parent=styles['Heading2'],
                fontName=font_bold,
                fontSize=14,
                spaceAfter=6 * mm,
                textColor=colors.HexColor(section_colors['general']),
                alignment=TA_LEFT
            )
        ))

        # Таблица общей статистики
        general_data = [
            ['Показатель', 'Значение', 'За 7 дней'],
            ['Всего статей', str(total_articles), f"+{recent_articles}"],
            ['Всего пользователей', str(total_users), f"+{recent_users}"],
            ['Всего просмотров', str(total_views), '-'],
            ['Всего комментариев', str(total_comments), '-']
        ]

        general_table = Table(general_data, colWidths=[80 * mm, 40 * mm, 30 * mm])
        general_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(section_colors['general'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), font_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 1), (-1, -1), font_normal),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [
                colors.HexColor('#ffffff'),
                colors.HexColor('#f8fafc')
            ]),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))

        story.append(general_table)
        story.append(Spacer(1, 15 * mm))

        # 2. Топ просматриваемых статей
        story.append(Paragraph(
            "🔥 ТОП ПРОСМАТРИВАЕМЫХ СТАТЕЙ",
            ParagraphStyle(
                'SectionTitle',
                parent=styles['Heading2'],
                fontName=font_bold,
                fontSize=14,
                spaceAfter=6 * mm,
                textColor=colors.HexColor(section_colors['top_viewed']),
                alignment=TA_LEFT
            )
        ))

        if top_viewed:
            viewed_data = [['№', 'Статья', 'Просмотры', 'Лайки']]
            for idx, article in enumerate(top_viewed, 1):
                # Обработка длинных заголовков
                title_text = article.title
                if len(title_text) > 60:
                    title_text = title_text[:57] + "..."

                title_lines = []
                words = title_text.split()
                current_line = ""
                for word in words:
                    if len(current_line) + len(word) + 1 <= 30:
                        current_line += f"{word} "
                    else:
                        if current_line:
                            title_lines.append(current_line.strip())
                        current_line = f"{word} "
                if current_line:
                    title_lines.append(current_line.strip())

                title_para = Paragraph("<br/>".join(title_lines), cell_style) if len(title_lines) > 1 else Paragraph(
                    title_text, cell_style)

                viewed_data.append([
                    Paragraph(str(idx), number_style),
                    title_para,
                    Paragraph(str(article.views_count), number_style),
                    Paragraph(str(article.likes.count()), number_style)
                ])

            viewed_table = Table(viewed_data, colWidths=[10 * mm, 100 * mm, 25 * mm, 25 * mm])
            viewed_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(section_colors['top_viewed'])),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), font_bold),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 1), (-1, -1), font_normal),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [
                    colors.HexColor('#ffffff'),
                    colors.HexColor('#f8fafc')
                ]),
            ]))
            story.append(viewed_table)
        else:
            story.append(Paragraph("Нет данных", cell_style))

        story.append(Spacer(1, 15 * mm))

        # 3. Топ лайкнутых статей
        story.append(Paragraph(
            "👍 ТОП ЛАЙКНУТЫХ СТАТЕЙ",
            ParagraphStyle(
                'SectionTitle',
                parent=styles['Heading2'],
                fontName=font_bold,
                fontSize=14,
                spaceAfter=6 * mm,
                textColor=colors.HexColor(section_colors['top_liked']),
                alignment=TA_LEFT
            )
        ))

        if top_liked:
            liked_data = [['№', 'Статья', 'Лайки', 'Просмотры']]
            for idx, article in enumerate(top_liked, 1):
                title_text = article.title
                if len(title_text) > 60:
                    title_text = title_text[:57] + "..."

                title_lines = []
                words = title_text.split()
                current_line = ""
                for word in words:
                    if len(current_line) + len(word) + 1 <= 30:
                        current_line += f"{word} "
                    else:
                        if current_line:
                            title_lines.append(current_line.strip())
                        current_line = f"{word} "
                if current_line:
                    title_lines.append(current_line.strip())

                title_para = Paragraph("<br/>".join(title_lines), cell_style) if len(title_lines) > 1 else Paragraph(
                    title_text, cell_style)

                liked_data.append([
                    Paragraph(str(idx), number_style),
                    title_para,
                    Paragraph(str(article.likes_count), number_style),
                    Paragraph(str(article.views_count), number_style)
                ])

            liked_table = Table(liked_data, colWidths=[10 * mm, 100 * mm, 25 * mm, 25 * mm])
            liked_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(section_colors['top_liked'])),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), font_bold),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 1), (-1, -1), font_normal),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [
                    colors.HexColor('#ffffff'),
                    colors.HexColor('#f8fafc')
                ]),
            ]))
            story.append(liked_table)
        else:
            story.append(Paragraph("Нет данных", cell_style))

        story.append(Spacer(1, 15 * mm))

        # 4. Популярные категории
        story.append(Paragraph(
            "🏷️ ПОПУЛЯРНЫЕ КАТЕГОРИИ",
            ParagraphStyle(
                'SectionTitle',
                parent=styles['Heading2'],
                fontName=font_bold,
                fontSize=14,
                spaceAfter=6 * mm,
                textColor=colors.HexColor(section_colors['categories']),
                alignment=TA_LEFT
            )
        ))

        if top_categories:
            categories_data = [['№', 'Категория', 'Просмотры', 'Статей']]
            for idx, category in enumerate(top_categories, 1):
                categories_data.append([
                    Paragraph(str(idx), number_style),
                    Paragraph(category.name, cell_style),
                    Paragraph(str(category.total_views or 0), number_style),
                    Paragraph(str(category.article_count or 0), number_style)
                ])

            categories_table = Table(categories_data, colWidths=[10 * mm, 80 * mm, 30 * mm, 25 * mm])
            categories_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(section_colors['categories'])),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), font_bold),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 1), (-1, -1), font_normal),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [
                    colors.HexColor('#ffffff'),
                    colors.HexColor('#f8fafc')
                ]),
            ]))
            story.append(categories_table)
        else:
            story.append(Paragraph("Нет данных", cell_style))

        story.append(Spacer(1, 15 * mm))

        # 5. Популярные поисковые запросы
        story.append(Paragraph(
            "🔍 ПОПУЛЯРНЫЕ ПОИСКОВЫЕ ЗАПРОСЫ",
            ParagraphStyle(
                'SectionTitle',
                parent=styles['Heading2'],
                fontName=font_bold,
                fontSize=14,
                spaceAfter=6 * mm,
                textColor=colors.HexColor(section_colors['searches']),
                alignment=TA_LEFT
            )
        ))

        if popular_searches:
            searches_data = [['№', 'Поисковый запрос', 'Количество']]
            for idx, search in enumerate(popular_searches, 1):
                query_text = search['query']
                if len(query_text) > 50:
                    query_text = query_text[:47] + "..."

                searches_data.append([
                    Paragraph(str(idx), number_style),
                    Paragraph(query_text, cell_style),
                    Paragraph(str(search['count']), number_style)
                ])

            searches_table = Table(searches_data, colWidths=[10 * mm, 100 * mm, 30 * mm])
            searches_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(section_colors['searches'])),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), font_bold),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 1), (-1, -1), font_normal),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [
                    colors.HexColor('#ffffff'),
                    colors.HexColor('#f8fafc')
                ]),
            ]))
            story.append(searches_table)
        else:
            story.append(Paragraph("Нет данных", cell_style))

        # Футер
        story.append(Spacer(1, 15 * mm))
        footer_text = (
            f"Сформировано: {timezone.now().strftime('%d.%m.%Y %H:%M')} | "
            f"Пользователь: {request.user.username} | "
            f"Форум 'ВЕДЬМАК' © {timezone.now().strftime('%Y')}"
        )
        story.append(Paragraph(
            footer_text,
            ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontName=font_normal,
                fontSize=8,
                textColor=colors.HexColor('#6b7280'),
                alignment=TA_CENTER
            )
        ))

        # Строим PDF
        doc.build(story)

        # Подготавливаем response
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        filename = f"statistics_report_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        # Кодируем имя файла для русских символов
        try:
            from urllib.parse import quote
            response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
        except:
            pass

        # Логируем действие
        ActionLogger.log_action(
            request=request,
            action_type='statistics_export',
            description=f'Экспорт статистики в PDF',
            extra_data={'format': 'pdf'}
        )

        return response

    except Exception as e:
        import traceback
        error_msg = f"Ошибка при создании PDF статистики: {str(e)}"
        print(error_msg)
        traceback.print_exc()

        # Fallback в TXT
        content = f"Ошибка при создании PDF: {str(e)}\n\n"
        content += f"СТАТИСТИКА ФОРУМА 'ВЕДЬМАК'\n"
        content += f"Дата: {timezone.now().strftime('%d.%m.%Y %H:%M')}\n"
        content += f"Всего статей: {total_articles}\n"
        content += f"Всего пользователей: {total_users}\n"
        content += f"Всего просмотров: {total_views}\n"

        response = HttpResponse(content, content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="statistics_backup.txt"'
        return response

@login_required
def export_statistics_json(request):
    """
    Экспорт статистики в формате JSON.
    Доступно только для администраторов (staff).
    """
    if not request.user.is_staff:
        return JsonResponse(
            {"error": "Доступ запрещен"},
            status=403
        )

    try:
        from django.db.models import Count, Sum
        from django.core.serializers.json import DjangoJSONEncoder

        # Топ 3 самых просматриваемых статей
        top_viewed = list(Article.objects.filter(
            status='published'
        ).order_by('-views_count')[:3].values('id', 'title', 'views_count'))

        # Топ 3 самых лайкнутых статей
        top_liked = list(Article.objects.filter(
            status='published'
        ).annotate(
            likes_count=Count('likes')
        ).order_by('-likes_count')[:3].values('id', 'title', 'likes_count'))

        # Топ 3 статей с комментариями
        top_commented = list(Article.objects.filter(
            status='published'
        ).annotate(
            comments_count=Count('comments')
        ).order_by('-comments_count')[:3].values('id', 'title', 'comments_count'))

        # Самые просматриваемые категории
        top_categories = list(Category.objects.filter(
            articles__status='published'
        ).annotate(
            total_views=Sum('articles__views_count'),
            article_count=Count('articles')
        ).filter(
            article_count__gt=0
        ).order_by('-total_views')[:5].values('id', 'name', 'total_views', 'article_count'))

        # Популярные поисковые запросы
        popular_searches = list(SearchQuery.objects.values('query').annotate(
            count=Count('id')
        ).order_by('-count')[:10])

        # Общая статистика
        total_articles = Article.objects.filter(status='published').count()
        total_users = User.objects.filter(is_active=True).count()
        total_comments = Comment.objects.count()
        total_views = Article.objects.filter(status='published').aggregate(
            total=Sum('views_count')
        )['total'] or 0

        # Статистика за последние 7 дней
        seven_days_ago = timezone.now() - timezone.timedelta(days=7)
        recent_articles = Article.objects.filter(
            created_at__gte=seven_days_ago,
            status='published'
        ).count()

        recent_users = User.objects.filter(
            date_joined__gte=seven_days_ago
        ).count()

        # Формируем JSON-структуру
        statistics_data = {
            "metadata": {
                "export_date": timezone.now().isoformat(),
                "format": "JSON",
                "generated_by": request.user.username,
                "forum_name": "Форум 'ВЕДЬМАК'"
            },
            "general_statistics": {
                "total_articles": total_articles,
                "total_users": total_users,
                "total_comments": total_comments,
                "total_views": total_views,
                "recent_articles_last_7_days": recent_articles,
                "recent_users_last_7_days": recent_users,
            },
            "top_articles": {
                "most_viewed": top_viewed,
                "most_liked": top_liked,
                "most_commented": top_commented,
            },
            "categories": {
                "most_viewed_categories": top_categories,
            },
            "search": {
                "popular_search_queries": popular_searches,
            }
        }

        # Создаем HttpResponse с JSON-данными
        response = JsonResponse(
            statistics_data,
            encoder=DjangoJSONEncoder,
            json_dumps_params={'indent': 2, 'ensure_ascii': False}
        )
        response['Content-Disposition'] = 'attachment; filename="witcher_forum_statistics.json"'
        response['Content-Type'] = 'application/json; charset=utf-8'

        # Логируем действие
        ActionLogger.log_action(
            request=request,
            action_type='statistics_export',
            description=f'Экспорт статистики в JSON',
            extra_data={'format': 'json', 'data_count': {
                'articles': total_articles,
                'users': total_users,
                'categories': len(top_categories),
                'searches': len(popular_searches)
            }}
        )

        return response

    except Exception as e:
        return JsonResponse(
            {"error": f"Ошибка при экспорте статистики: {str(e)}"},
            status=500
        )


@require_POST
@login_required
def comment_like(request, comment_id):
    """Обработка лайка на комментарий. Только для аутентифицированных пользователей."""
    try:
        comment = get_object_or_404(Comment, id=comment_id)

        # Проверяем, есть ли уже лайк от пользователя
        was_liked = comment.is_liked_by_user(request.user)

        # Переключаем лайк с помощью метода из модели
        liked = comment.toggle_like(request.user)
        likes_count = comment.like_count

        # Логируем действие
        ActionLogger.log_action(
            request=request,
            action_type='comment_like_add' if liked else 'comment_like_remove',
            description=f'Пользователь {request.user.username} {"поставил" if liked else "убрал"} лайк комментарию',
            target_object=comment,
            extra_data={
                'comment_id': comment.id,
                'article_title': comment.article.title,
                'was_liked': was_liked,
                'now_liked': liked,
                'total_likes': likes_count,
            }
        )

        return JsonResponse({
            'success': True,
            'liked': liked,
            'likes_count': likes_count,
            'was_liked': was_liked,
            'status_changed': was_liked != liked
        })
    except Comment.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Комментарий не найден'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def user_statistics(request, username=None):
    if username:
        profile_user = get_object_or_404(User, username=username)
        # Проверяем права доступа (только свои или админ может смотреть)
        if not request.user.is_staff and request.user != profile_user:
            return redirect('wiki:statistics')
    else:
        profile_user = request.user

    # Фильтр
    filter_type = request.GET.get('filter', 'all')  # all, week, month, year

    date_filter = Q()
    if filter_type == 'week':
        date_filter = Q(created_at__gte=timezone.now() - timezone.timedelta(days=7))
    elif filter_type == 'month':
        date_filter = Q(created_at__gte=timezone.now() - timezone.timedelta(days=30))
    elif filter_type == 'year':
        date_filter = Q(created_at__gte=timezone.now() - timezone.timedelta(days=365))

    # Статьи пользователя с фильтром
    user_articles = Article.objects.filter(
        author=profile_user
    ).filter(
        date_filter if filter_type != 'all' else Q()
    )

    # Статистика статей - аннотируем количество лайков
    article_stats = user_articles.annotate(
        article_like_count=Count('likes')  # переименуем, чтобы избежать конфликта
    ).order_by('-views_count')

    top_articles_by_views = article_stats[:10]
    top_articles_by_likes = article_stats.order_by('-article_like_count')[:10]

    # Комментарии пользователя
    user_comments = Comment.objects.filter(
        author=profile_user
    ).filter(
        date_filter if filter_type != 'all' else Q()
    ).annotate(
        comment_like_count=Count('comment_likes')
    ).order_by('-comment_like_count')[:10]

    # Общая статистика
    total_articles = user_articles.count()
    total_views = user_articles.aggregate(total_views=Sum('views_count'))['total_views'] or 0
    total_likes_articles = user_articles.aggregate(
        total_likes=Count('likes')
    )['total_likes'] or 0
    total_likes_comments = user_comments.aggregate(
        total_likes=Count('comment_likes')
    )['total_likes'] or 0

    context = {
        'profile_user': profile_user,
        'filter_type': filter_type,
        'top_articles_by_views': top_articles_by_views,
        'top_articles_by_likes': top_articles_by_likes,
        'user_comments': user_comments,
        'total_articles': total_articles,
        'total_views': total_views,
        'total_likes_articles': total_likes_articles,
        'total_likes_comments': total_likes_comments,
        'total_likes': total_likes_articles + total_likes_comments,
    }

    return render(request, 'wiki/user_statistics.html', context)

@staff_member_required
def censorship_dashboard(request):
    """Дашборд цензуры для администраторов"""
    # Можно добавить статистику и логи
    return render(request, 'wiki/censorship_dashboard.html', {
        'word_count': CensorshipService.get_banned_words_count(),
        'banned_words_examples': CensorshipService.BANNED_WORDS[:20],
    })


def censorship_info(request):
    """Информация о системе цензуры"""
    word_count = CensorshipService.get_banned_words_count()

    # Примеры запрещенных слов (первые 20)
    examples = CensorshipService.BANNED_WORDS[:20]

    return render(request, 'wiki/censorship_info.html', {
        'word_count': word_count,
        'examples': examples,
    })


@login_required
def my_censorship_warnings(request):
    """Показывает предупреждения пользователя за нецензурную лексику"""
    warning_count = CensorshipWarningSystem.get_user_warnings(request.user)

    # Определяем уровень серьезности
    level = CensorshipWarningSystem.get_punishment_level(warning_count)

    # Цвета для разных уровней
    level_colors = {
        'warning': 'primary',
        'warning_strong': 'warning',
        'warning_critical': 'danger',
        'temp_ban_1h': 'danger',
        'temp_ban_24h': 'dark',
    }

    # Сообщение в зависимости от уровня
    level_messages = {
        'warning': '🚫 У вас есть предупреждение',
        'warning_strong': '⚠️ У вас есть серьезное предупреждение',
        'warning_critical': '🔴 Критическое предупреждение',
        'temp_ban_1h': '⏰ Временная блокировка (1 час)',
        'temp_ban_24h': '🚨 Аккаунт заблокирован (24 часа)',
    }

    return render(request, 'wiki/censorship_warnings.html', {
        'warning_count': warning_count,
        'level': level,
        'level_color': level_colors.get(level, 'secondary'),
        'level_message': level_messages.get(level, 'Информация'),
        'next_level_warnings': 5 - warning_count if warning_count < 5 else 0,
    })


@staff_member_required
def reset_user_warnings(request, user_id):
    """Сброс предупреждений пользователя (только для админов)"""
    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        CensorshipWarningSystem.reset_user_warnings(user)
        messages.success(request, f'Предупреждения пользователя {user.username} сброшены.')
        return redirect('wiki:user_warnings_list')

    return render(request, 'wiki/reset_warnings_confirm.html', {'user': user})


@staff_member_required
def user_warnings_list(request):
    """Список пользователей с предупреждениями (только для админов)"""
    # В реальном проекте здесь была бы БД, но пока используем кэш
    users_with_warnings = []

    # Простой способ - можно доработать с БД позже
    for user in User.objects.filter(is_active=True):
        warnings = CensorshipWarningSystem.get_user_warnings(user)
        if warnings > 0:
            users_with_warnings.append({
                'user': user,
                'warnings': warnings,
                'level': CensorshipWarningSystem.get_punishment_level(warnings),
            })

    # Сортируем по количеству предупреждений
    users_with_warnings.sort(key=lambda x: x['warnings'], reverse=True)

    return render(request, 'wiki/user_warnings_list.html', {
        'users_with_warnings': users_with_warnings,
    })


def banned_page(request):
    """Страница информации о бане"""
    if not request.user.is_authenticated:
        return redirect('wiki:login')  # Используем wiki:login

    try:
        # Получаем активные баны пользователя
        active_bans = UserBan.objects.filter(
            user=request.user,
            is_active=True
        )

        if not active_bans.exists():
            # Если нет активных банов - редирект на главную
            return redirect('wiki:home')  # Используем wiki:home вместо home

        # Берем первый активный бан
        ban = active_bans.first()

        # Проверяем не истек ли бан
        if ban.duration != 'permanent' and ban.expires_at:
            if ban.expires_at <= timezone.now():
                # Бан истек - деактивируем
                ban.is_active = False
                ban.save()
                return redirect('wiki:home')  # Используем wiki:home вместо home

        # Формируем контекст
        time_remaining = None
        if ban.duration != 'permanent' and ban.expires_at:
            remaining = ban.expires_at - timezone.now()
            if remaining.total_seconds() > 0:
                time_remaining = remaining

        context = {
            'ban': ban,
            'time_remaining': time_remaining,
            'is_permanent': ban.duration == 'permanent',
        }

        return render(request, 'wiki/banned.html', context)

    except Exception as e:
        print(f"DEBUG: Error in banned_page: {e}")
        return redirect('wiki:home')  # Используем wiki:home вместо home

def check_user_ban(user):
    """Проверяет, забанен ли пользователь"""
    if not user.is_authenticated:
        return None

    active_ban = UserBan.objects.filter(
        user=user,
        is_active=True
    ).first()

    if active_ban and not active_ban.is_expired():
        return active_ban

    return None

@login_required
def moderation_panel(request):
    if not request.user.has_perm('wiki.moderate_content'):
        messages.error(request, 'У вас нет прав для доступа к панели модерации')
        return redirect('index')

