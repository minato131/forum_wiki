from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile, Article
from django.core.mail import send_mail
from django.conf import settings
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.core.management import call_command

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Автоматически создает профиль при создании пользователя"""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Автоматически сохраняет профиль при сохранении пользователя"""
    if hasattr(instance, 'profile'):
        instance.profile.save()


@receiver(post_save, sender=Article)
def handle_article_status_change(sender, instance, created, **kwargs):
    """Обработка изменения статуса статьи"""
    if not created:  # Только при изменениях
        try:
            old_instance = Article.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                send_article_status_notification(instance, old_instance.status)
        except Article.DoesNotExist:
            pass


def send_article_status_notification(article, old_status):
    """Отправка уведомления автору о изменении статуса"""
    status_messages = {
        'published': {
            'subject': '🎉 Ваша статья опубликована!',
            'message': f'Поздравляем! Ваша статья "{article.title}" была одобрена и опубликована.'
        },
        'needs_correction': {
            'subject': '✏️ Требуются правки в вашей статье',
            'message': f'Ваша статья "{article.title}" требует доработки. Пожалуйста, ознакомьтесь с замечаниями модератора.'
        },
        'editor_review': {
            'subject': '📝 Статья отправлена редактору',
            'message': f'Ваша статья "{article.title}" была отправлена редактору для исправления.'
        },
        'author_review': {
            'subject': '📋 Доступна исправленная версия статьи',
            'message': f'Редактор внес правки в вашу статью "{article.title}". Пожалуйста, ознакомьтесь и согласуйте изменения.'
        },
        'rejected': {
            'subject': '❌ Статья отклонена',
            'message': f'К сожалению, ваша статья "{article.title}" была отклонена.'
        }
    }

    status_info = status_messages.get(article.status, {})

    if status_info:
        subject = status_info['subject']
        message = f"""
        Здравствуйте, {article.author.username}!

        {status_info['message']}

        {f'Замечания модератора: {article.moderation_notes}' if article.moderation_notes else ''}
        {f'Заметки редактора: {article.editor_notes}' if article.editor_notes else ''}

        Посмотреть статью: http://127.0.0.1:8000{article.get_absolute_url()}
        {f'Согласовать правки: http://127.0.0.1:8000/article/{article.slug}/author-review/' if article.status == 'author_review' else ''}

        С уважением,
        Команда Форума по Вселенной Ведьмака
        """

        try:
            send_mail(
                subject,
                message,
                getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@witcher-forum.ru'),
                [article.author.email],
                fail_silently=True,
            )
            print(f"✅ Уведомление отправлено автору {article.author.email}")
        except Exception as e:
            print(f"❌ Ошибка отправки email: {e}")

@receiver(post_migrate)
def create_default_categories(sender, **kwargs):
    """
    Автоматически создает базовые категории после миграций
    """
    if sender.name == 'wiki':
        from wiki.models import Category
        # Проверяем, есть ли уже категории
        if not Category.objects.exists():
            call_command('create_default_categories')