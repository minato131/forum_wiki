# wiki/utils/stats_collector.py
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, Max
from django.contrib.auth import get_user_model
from ..models import Article, Category, Comment, ArticleStat, CategoryStat, SearchQuery, SiteStat, SearchHistory

User = get_user_model()


class StatsCollector:
    """Сборщик статистики"""

    @staticmethod
    def update_article_stats(article_id):
        """Обновление статистики для конкретной статьи"""
        try:
            article = Article.objects.get(id=article_id)

            # Получаем актуальные данные
            views = article.views_count
            likes = article.likes.count()  # Используем related_name 'likes'
            comments_count = article.comments.count()

            # Обновляем или создаем запись
            stat, created = ArticleStat.objects.update_or_create(
                article=article,
                defaults={
                    'views': views,
                    'likes': likes,
                    'comments_count': comments_count,
                }
            )

            return stat
        except Article.DoesNotExist:
            return None

    @staticmethod
    def update_category_stats(category_id):
        """Обновление статистики для категории"""
        try:
            category = Category.objects.get(id=category_id)
            articles = category.articles.filter(status='published')

            total_views = sum(article.views_count for article in articles)
            total_articles = articles.count()

            # Считаем средний рейтинг (по лайкам)
            if total_articles > 0:
                total_likes = sum(article.likes.count() for article in articles)
                avg_rating = total_likes / total_articles
            else:
                avg_rating = 0.0

            stat, created = CategoryStat.objects.update_or_create(
                category=category,
                defaults={
                    'total_views': total_views,
                    'total_articles': total_articles,
                    'avg_rating': avg_rating,
                }
            )

            return stat
        except Category.DoesNotExist:
            return None

    @staticmethod
    def log_search_query(query, user=None, ip_address=None, user_agent=None, request=None):
        """Логирует поисковый запрос"""
        try:
            # Если передан request, извлекаем данные из него
            if request:
                ip_address = ip_address or request.META.get('REMOTE_ADDR')
                user_agent = user_agent or request.META.get('HTTP_USER_AGENT', '')
                user = user or (request.user if request.user.is_authenticated else None)

            # Сохраняем в SearchQuery (для статистики популярности)
            search_query, created = SearchQuery.objects.get_or_create(query=query)
            if not created:
                search_query.count += 1
                search_query.save()

            # Сохраняем в SearchHistory (для детальной истории)
            if user or ip_address:  # Сохраняем только если есть пользователь или IP
                SearchHistory.objects.create(
                    query=query,
                    user=user,
                    results_count=0,  # Можно обновить позже
                    ip_address=ip_address,
                    user_agent=user_agent or ''
                )

        except Exception as e:
            print(f"Ошибка при логировании поискового запроса: {e}")

    @staticmethod
    def update_daily_stats():
        """Обновление дневной статистики сайта"""
        today = timezone.now().date()

        total_views = Article.objects.filter(status='published').aggregate(
            total=Sum('views_count')
        )['total'] or 0

        total_users = User.objects.filter(is_active=True).count()
        total_articles = Article.objects.filter(status='published').count()
        total_comments = Comment.objects.count()

        # Активные пользователи за последние 30 дней
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        active_users = User.objects.filter(
            last_login__gte=thirty_days_ago
        ).count()

        stat, created = SiteStat.objects.update_or_create(
            date=today,
            defaults={
                'total_views': total_views,
                'total_users': total_users,
                'total_articles': total_articles,
                'total_comments': total_comments,
                'active_users': active_users,
            }
        )

        return stat

    @staticmethod
    def get_top_stats():
        """Получение топовой статистики"""
        # Топ 3 самых просматриваемых статей
        top_viewed = Article.objects.filter(
            status='published'
        ).order_by('-views_count')[:3]

        # Топ 3 самых лайкнутых статей - нужно считать через аннотацию
        top_liked = Article.objects.filter(
            status='published'
        ).annotate(
            likes_count=Count('likes')
        ).order_by('-likes_count')[:3]

        # Топ 3 статей с самым большим количеством комментариев
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

        # Самые популярные поисковые запросы
        popular_searches = SearchQuery.objects.values('query').annotate(
            count=Count('id'),
            last_search=Max('created_at')
        ).order_by('-count')[:10]

        return {
            'top_viewed': top_viewed,
            'top_liked': top_liked,
            'top_commented': top_commented,
            'top_categories': top_categories,
            'popular_searches': popular_searches,
        }


class StatsMiddleware:
    """Middleware для сбора статистики"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Логируем поисковые запросы
        if 'q' in request.GET and request.GET['q'].strip():
            query = request.GET['q'].strip()
            user = request.user if request.user.is_authenticated else None
            StatsCollector.log_search_query(query, user, request=request)

        return response