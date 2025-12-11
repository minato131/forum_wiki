from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile, Article, Backup, BackupLog, ActionLog
from django.core.mail import send_mail
from django.conf import settings
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.core.management import call_command
from django.utils import timezone


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Автоматически создает профиль при создании пользователя"""
    if created:
        UserProfile.objects.create(user=instance)
        # Логируем создание профиля
        ActionLog.objects.create(
            user=instance,
            action_type='profile_create',
            description=f'Автоматически создан профиль для пользователя {instance.username}',
            action_data={'user_id': instance.id, 'username': instance.username}
        )


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
                # Логируем изменение статуса
                ActionLog.objects.create(
                    user=instance.author,
                    action_type='article_status_change',
                    description=f'Изменен статус статьи "{instance.title}" с {old_instance.status} на {instance.status}',
                    action_data={
                        'article_id': instance.id,
                        'article_title': instance.title,
                        'old_status': old_instance.status,
                        'new_status': instance.status,
                        'slug': instance.slug
                    }
                )
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
            # Логируем отправку уведомления
            ActionLog.objects.create(
                user=article.author,
                action_type='email_notification_sent',
                description=f'Отправлено уведомление о смене статуса статьи "{article.title}"',
                action_data={
                    'article_id': article.id,
                    'article_title': article.title,
                    'notification_type': article.status,
                    'recipient_email': article.author.email
                }
            )
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
            # Логируем создание категорий
            ActionLog.objects.create(
                user=None,
                action_type='system_initialization',
                description='Созданы стандартные категории при миграции',
                action_data={'app': 'wiki'}
            )


# ========== НОВЫЕ СИГНАЛЫ ДЛЯ ЛОГИРОВАНИЯ БЭКАПОВ ==========

@receiver(post_save, sender=Backup)
def log_backup_creation(sender, instance, created, **kwargs):
    """Логирует создание и изменение бэкапов"""
    if created:
        # Логируем создание бэкапа
        action_type = 'backup_created'
        description = f'Создана резервная копия "{instance.name}" ({instance.backup_type})'

        # Создаем запись в ActionLog
        ActionLog.objects.create(
            user=kwargs.get('user'),  # Должен передаваться из view при создании
            action_type=action_type,
            description=description,
            action_data={
                'backup_id': instance.id,
                'backup_name': instance.name,
                'backup_type': instance.backup_type,
                'file_size': instance.file_size,
                'file_size_display': instance.file_size_display(),
                'status': instance.status,
                'file_path': instance.file_path,
            }
        )

        # Также создаем BackupLog для истории бэкапов
        BackupLog.objects.create(
            backup=instance,
            log_type='created',
            message=description,
            details={
                'backup_id': instance.id,
                'name': instance.name,
                'type': instance.backup_type,
                'size': instance.file_size_display(),
                'path': instance.file_path,
                'status': instance.status,
            }
        )

        print(f"✅ Лог бэкапа создан: {description}")

    else:
        # Логируем изменение статуса бэкапа
        try:
            old_instance = Backup.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                action_type = 'backup_status_changed'
                description = f'Изменен статус бэкапа "{instance.name}" с {old_instance.status} на {instance.status}'

                ActionLog.objects.create(
                    user=kwargs.get('user'),
                    action_type=action_type,
                    description=description,
                    action_data={
                        'backup_id': instance.id,
                        'backup_name': instance.name,
                        'old_status': old_instance.status,
                        'new_status': instance.status,
                    }
                )

                BackupLog.objects.create(
                    backup=instance,
                    log_type='status_change',
                    message=description,
                    details={
                        'backup_id': instance.id,
                        'name': instance.name,
                        'old_status': old_instance.status,
                        'new_status': instance.status,
                    }
                )

                print(f"✅ Лог изменения статуса бэкапа: {description}")

        except Backup.DoesNotExist:
            pass


@receiver(post_save, sender=BackupLog)
def log_backup_log_creation(sender, instance, created, **kwargs):
    """Логирует создание записи в логах бэкапов"""
    if created:
        try:
            description = f'Создан лог операции с бэкапом: {instance.get_log_type_display()}'

            # Для ActionLog определяем тип операции
            log_type_to_action = {
                'created': 'backup_log_created',
                'restored': 'backup_log_restored',
                'deleted': 'backup_log_deleted',
                'downloaded': 'backup_log_downloaded',
                'error': 'backup_log_error',
            }

            action_type = log_type_to_action.get(instance.log_type, 'backup_log_general')

            ActionLog.objects.create(
                user=instance.user,
                action_type=action_type,
                description=description,
                action_data={
                    'log_id': instance.id,
                    'log_type': instance.log_type,
                    'backup_id': instance.backup.id if instance.backup else None,
                    'backup_name': instance.backup.name if instance.backup else 'Не указан',
                    'message': instance.message,
                    'details': instance.details,
                }
            )

            print(f"✅ Лог операции с бэкапом: {description}")

        except Exception as e:
            print(f"❌ Ошибка логирования backup log: {e}")


@receiver(post_delete, sender=Backup)
def log_backup_deletion(sender, instance, **kwargs):
    """Логирует удаление бэкапа"""
    try:
        description = f'Удалена резервная копия "{instance.name}"'

        ActionLog.objects.create(
            user=None,  # Должен быть передан через контекст
            action_type='backup_deleted',
            description=description,
            action_data={
                'backup_name': instance.name,
                'backup_type': instance.backup_type,
                'file_size': instance.file_size,
                'created_at': instance.created_at.isoformat(),
            }
        )

        # Также создаем запись в BackupLog
        BackupLog.objects.create(
            backup=None,  # Бэкап уже удален
            log_type='deleted',
            user=None,  # Должен быть передан через контекст
            message=description,
            details={
                'backup_name': instance.name,
                'type': instance.backup_type,
                'size': instance.file_size_display(),
                'created_at': instance.created_at.isoformat(),
                'deleted_at': timezone.now().isoformat(),
            }
        )

        print(f"✅ Лог удаления бэкапа: {description}")

    except Exception as e:
        print(f"❌ Ошибка логирования удаления бэкапа: {e}")


# ========== СИГНАЛЫ ДЛЯ ЛОГИРОВАНИЯ ДРУГИХ ДЕЙСТВИЙ ==========

@receiver(post_save, sender=ActionLog)
def log_action_log_creation(sender, instance, created, **kwargs):
    """Логирует создание логов действий (мета-логирование)"""
    if created:
        # Только для отладки
        print(f"📝 ActionLog created: {instance.action_type} - {instance.description[:50]}...")


# ========== СИГНАЛЫ ДЛЯ ОПРЕДЕЛЕНИЯ ИНИЦИАТОРА ==========

def get_request_user():
    """Вспомогательная функция для получения пользователя из текущего запроса"""
    from django.utils.deprecation import MiddlewareMixin

    class RequestUserMiddleware(MiddlewareMixin):
        """Middleware для хранения пользователя в локальном контексте"""
        _user = None

        def process_request(self, request):
            RequestUserMiddleware._user = request.user if request.user.is_authenticated else None

        def process_response(self, request, response):
            RequestUserMiddleware._user = None
            return response

    return RequestUserMiddleware._user