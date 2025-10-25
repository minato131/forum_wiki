from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Sum
from django.core.paginator import Paginator
from django.utils.text import slugify
from django.contrib import messages
from django.utils import timezone
import os
import re
from .forms import ArticleForm, CommentForm, SearchForm, CategoryForm, ProfileUpdateForm
from .models import Article, Category, Comment, ArticleMedia, UserProfile, User, ArticleLike, ModerationComment, SearchQuery
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
import json
from django.utils import timezone
from django.contrib import messages
from django.http import JsonResponse

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
    results = []
    total_count = 0

    if query:
        # Сохраняем поисковый запрос
        search_query_obj, created = SearchQuery.objects.get_or_create(query=query)
        if not created:
            search_query_obj.increment()

        # Улучшенный поиск
        search_query = Q(title__icontains=query) | Q(content__icontains=query) | Q(excerpt__icontains=query)

        # Поиск по тегам
        try:
            search_query |= Q(tags__name__icontains=query)
        except:
            pass

        results = Article.objects.filter(search_query, status='published').distinct()

        # Фильтр по категории
        if category_filter:
            results = results.filter(categories__slug=category_filter)

        total_count = results.count()

        # Сортировка по релевантности
        title_matches = results.filter(title__icontains=query)
        other_matches = results.exclude(title__icontains=query)
        results = list(title_matches) + list(other_matches)

        # Пагинация
        paginator = Paginator(results, 10)
        page_number = request.GET.get('page')
        results = paginator.get_page(page_number)

    # Получаем популярные запросы (топ-10)
    popular_queries = SearchQuery.objects.all().order_by('-count', '-last_searched')[:10]

    # Получаем категории для фильтра
    categories = Category.objects.all()

    context = {
        'query': query,
        'category_filter': category_filter,
        'results': results,
        'total_count': total_count,
        'categories': categories,
        'popular_queries': popular_queries,
    }
    return render(request, 'wiki/search.html', context)


@login_required
def profile(request):
    """Страница профиля пользователя с возможностью редактирования"""
    # Получаем или создаем профиль пользователя
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = ProfileUpdateForm(
            request.POST,
            request.FILES,
            instance=user_profile,
            user=request.user
        )
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Ваш профиль был успешно обновлен!')
            return redirect('wiki:profile')
        else:
            messages.error(request, '❌ Пожалуйста, исправьте ошибки в форме.')
    else:
        form = ProfileUpdateForm(instance=user_profile, user=request.user)

    # Статистика пользователя
    user_articles_count = request.user.articles.count()
    published_articles_count = request.user.articles.filter(status='published').count()

    # Количество лайков пользователя
    liked_articles_count = ArticleLike.objects.filter(user=request.user).count()

    # Общее количество просмотров статей пользователя
    total_views = request.user.articles.aggregate(total_views=Sum('views_count'))['total_views'] or 0

    # Последние статьи пользователя
    recent_articles = request.user.articles.filter(status='published').order_by('-created_at')[:5]

    context = {
        'form': form,
        'user': request.user,
        'user_profile': user_profile,
        'user_articles_count': user_articles_count,
        'published_articles_count': published_articles_count,
        'liked_articles_count': liked_articles_count,
        'total_views': total_views,
        'recent_articles': recent_articles,
    }
    return render(request, 'wiki/profile.html', context)


@login_required
def article_create(request):
    """Создание новой статьи"""
    error_message = ""
    success_message = ""

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        excerpt = request.POST.get('excerpt', '').strip()
        category_ids = request.POST.getlist('categories')

        # Очищаем контент от LaTeX
        content = clean_latex_from_content(content)
        excerpt = clean_latex_from_content(excerpt)

        # Упрощенная проверка - только is_staff
        if request.user.is_staff:
            status = 'published'  # Админы публикуют сразу
        else:
            status = 'review'  # Обычные пользователи отправляют на модерацию

        if title and content:
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

            # Добавляем категории
            if category_ids:
                categories = Category.objects.filter(id__in=category_ids)
                article.categories.set(categories)

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
                success_message = "Статья отправлена на модерацию. После проверки она будет опубликована."
                return render(request, 'wiki/article_create.html', {
                    'categories': Category.objects.all(),
                    'success_message': success_message
                })
            else:
                return redirect('wiki:article_detail', slug=article.slug)
        else:
            error_message = "Пожалуйста, заполните все обязательные поля."

    # Получаем все категории для формы
    categories = Category.objects.all()

    context = {
        'categories': categories,
        'error_message': error_message,
        'success_message': success_message,
    }
    return render(request, 'wiki/article_create.html', context)


def article_detail(request, slug):
    article = get_object_or_404(Article, slug=slug)

    # Проверяем права на просмотр
    if article.status != 'published' and not article.can_edit(request.user):
        return render(request, 'wiki/access_denied.html', {
            'message': 'У вас нет прав для просмотра этой статьи.'
        })

    # Увеличиваем счетчик просмотров только для опубликованных статей
    if article.status == 'published' and hasattr(article, 'views_count'):
        article.views_count += 1
        article.save(update_fields=['views_count'])

    # Получаем медиафайлы статьи с сортировкой
    media_files = article.media_files.all().order_by('display_order', 'uploaded_at')

    # Получаем комментарии к статье
    comments = article.comments.filter(is_approved=True, parent__isnull=True).order_by('created_at')

    # Форма для добавления комментария
    comment_form = CommentForm()
    print(f"DEBUG: Article: {article.title}")
    print(f"DEBUG: Comments count: {article.comments.count()}")
    if request.method == 'POST' and request.user.is_authenticated:
        print(f"DEBUG: POST request received from {request.user.username}")
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            print(f"DEBUG: Form is valid")
            comment = comment_form.save(commit=False)
            comment.article = article
            comment.author = request.user
            print(f"DEBUG: Comment content: {comment.content}")

            # ... остальной код ...

            comment.save()
            print(f"DEBUG: Comment saved with ID: {comment.id}")
            messages.success(request, 'Комментарий добавлен!')

            # После сохранения перезагружаем комментарии
            comments = article.comments.filter(is_approved=True, parent__isnull=True).order_by('created_at')
            print(f"DEBUG: Comments after save: {comments.count()}")

            # Очищаем форму
            comment_form = CommentForm()
        else:
            print(f"DEBUG: Form errors: {comment_form.errors}")
            messages.error(request, 'Ошибка при добавлении комментария. Проверьте форму.')

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

            # После сохранения перезагружаем комментарии
            comments = article.comments.filter(is_approved=True, parent__isnull=True).order_by('created_at')

            # Очищаем форму
            comment_form = CommentForm()
        else:
            messages.error(request, 'Ошибка при добавлении комментария. Проверьте форму.')

    context = {
        'article': article,
        'media_files': media_files,
        'comments': comments,
        'comment_form': comment_form,
        'can_edit': article.can_edit(request.user),
        'can_moderate': article.can_moderate(request.user),
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

    error_message = ""
    success_message = ""

    if request.method == 'POST':
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

    if not article.can_moderate(request.user):
        return render(request, 'wiki/access_denied.html', {
            'message': 'У вас нет прав для модерации статей.'
        })

    if request.method == 'POST':
        action = request.POST.get('action')
        moderation_notes = request.POST.get('moderation_notes', '').strip()
        highlighted_corrections = request.POST.get('highlighted_corrections', '')

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

        elif action == 'reject':
            article.status = 'rejected'
            article.moderated_by = request.user
            article.moderated_at = timezone.now()
            article.moderation_notes = moderation_notes
            article.save()
            messages.success(request, f'Статья "{article.title}" отклонена.')

        return redirect('wiki:moderation_queue')

    # Получаем существующие комментарии модерации
    moderation_comments = article.moderation_comments.filter(resolved=False)

    context = {
        'article': article,
        'moderation_comments': moderation_comments,
    }
    return render(request, 'wiki/article_moderate.html', context)


# В views.py ДОБАВИТЬ новые функции модерации

@login_required
def article_moderate(request, slug):
    """Расширенная модерация статьи с возможностью выделения текста"""
    article = get_object_or_404(Article, slug=slug)

    if not article.can_moderate(request.user):
        return render(request, 'wiki/access_denied.html', {
            'message': 'У вас нет прав для модерации статей.'
        })

    if request.method == 'POST':
        action = request.POST.get('action')
        moderation_notes = request.POST.get('moderation_notes', '').strip()
        highlighted_corrections = request.POST.get('highlighted_corrections', '')

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
    moderation_comments = article.moderation_comments.filter(resolved=False)

    context = {
        'article': article,
        'moderation_comments': moderation_comments,
    }
    return render(request, 'wiki/article_moderate.html', context)


@login_required
def add_moderation_comment(request, slug):
    """Добавление комментария к выделенному тексту"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        article = get_object_or_404(Article, slug=slug)

        if not article.can_moderate(request.user):
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


@login_required
def author_review(request, slug):
    """Страница для автора - согласование исправлений"""
    article = get_object_or_404(Article, slug=slug)

    if request.user != article.author:
        return render(request, 'wiki/access_denied.html', {
            'message': 'Вы не автор этой статьи.'
        })

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'accept':
            article.status = 'published'
            article.published_at = timezone.now()
            article.author_notes = 'Исправления редактора приняты'
            article.save()
            messages.success(request, 'Статья опубликована с исправлениями редактора.')

        elif action == 'reject':
            article.status = 'draft'
            article.author_notes = request.POST.get('author_notes', '')
            article.save()
            messages.success(request, 'Исправления отклонены. Статья возвращена в черновики.')

        return redirect('wiki:my_articles')

    context = {
        'article': article,
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
    """Регистрация нового пользователя"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Автоматически входим после регистрации
            messages.success(request, f'✅ Аккаунт создан! Добро пожаловать, {user.username}!')
            return redirect('wiki:home')
        else:
            messages.error(request, '❌ Пожалуйста, исправьте ошибки в форме.')
    else:
        form = UserCreationForm()

    context = {
        'form': form,
    }
    return render(request, 'wiki/register.html', context)


def user_public_profile(request, username):
    """Публичный профиль пользователя"""
    user = get_object_or_404(User, username=username)

    # Получаем профиль пользователя
    try:
        user_profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        user_profile = None

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
            liked = article.toggle_like(request.user)
            likes_count = article.get_likes_count()

            return JsonResponse({
                'success': True,
                'liked': liked,
                'likes_count': likes_count
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

        if not article.can_moderate(request.user):
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


@login_required
def author_review(request, slug):
    """Страница для автора - согласование исправлений"""
    article = get_object_or_404(Article, slug=slug)

    if request.user != article.author:
        return render(request, 'wiki/access_denied.html', {
            'message': 'Вы не автор этой статьи.'
        })

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'accept':
            article.status = 'published'
            article.published_at = timezone.now()
            article.author_notes = 'Исправления редактора приняты'
            article.save()
            messages.success(request, 'Статья опубликована с исправлениями редактора.')

        elif action == 'reject':
            article.status = 'draft'
            article.author_notes = request.POST.get('author_notes', '')
            article.save()
            messages.success(request, 'Исправления отклонены. Статья возвращена в черновики.')

        return redirect('wiki:my_articles')

    context = {
        'article': article,
    }
    return render(request, 'wiki/author_review.html', context)
# views.py - ОБНОВИТЬ функции проверки прав

def can_moderate(user):
    """Проверяет, может ли пользователь модерировать статьи"""
    return (user.is_staff or
            user.groups.filter(name__in=['Модератор', 'Администратор']).exists())

def can_edit_content(user):
    """Проверяет, может ли пользователь редактировать контент как редактор"""
    return (user.is_staff or
            user.groups.filter(name__in=['Редактор', 'Модератор', 'Администратор']).exists())

# Обновим функцию moderation_queue
@login_required
def moderation_queue(request):
    """Очередь статей на модерацию - только для модераторов"""
    if not can_moderate(request.user):
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
        'user_can_moderate': can_moderate(request.user),
        'user_can_edit': can_edit_content(request.user),
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