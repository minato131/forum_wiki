from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.text import slugify
from django_ckeditor_5.fields import CKEditor5Field
from taggit.managers import TaggableManager
import random
import string
from django.utils import timezone
from datetime import timedelta


class Category(models.Model):
    name = models.CharField('Название', max_length=100)
    slug = models.SlugField('URL', unique=True)
    description = models.TextField('Описание', blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                               verbose_name='Родительская категория', related_name='children')
    image = models.ImageField('Изображение', upload_to='categories/', blank=True, null=True)

    # Новые поля для основных категорий
    is_featured = models.BooleanField('Основная категория', default=False,
                                      help_text='Показывать в разделе основных категорий на главной странице')
    display_order = models.IntegerField('Порядок отображения', default=0,
                                        help_text='Чем меньше число, тем выше в списке')
    icon = models.CharField('Иконка', max_length=50, blank=True,
                            help_text='Эмодзи или код иконки (например: ⚔️, 👤, 🐺)')

    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('wiki:category_detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_article_count(self):
        return self.articles.count()

    def get_children_count(self):
        return self.children.count()


class Article(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('review', 'На модерации'),
        ('needs_correction', 'Требует правок'),
        ('editor_review', 'На проверке у редактора'),
        ('author_review', 'На согласовании у автора'),
        ('published', 'Опубликовано'),
        ('rejected', 'Отклонено'),
        ('archived', 'Архив'),
    ]

    # Основные поля
    title = models.CharField('Заголовок', max_length=200)
    slug = models.SlugField('URL', unique=True, max_length=200)
    content = CKEditor5Field('Содержание', config_name='extends')
    excerpt = models.TextField('Краткое описание', max_length=500, blank=True)
    featured_image = models.ImageField('Главное изображение', upload_to='articles/', blank=True, null=True)

    # Поля для системы модерации
    editor_notes = models.TextField('Заметки редактора', blank=True)
    author_notes = models.TextField('Заметки автора', blank=True)
    correction_deadline = models.DateTimeField('Срок исправления', null=True, blank=True)
    highlighted_corrections = models.JSONField('Выделенные правки', blank=True, null=True,
                                               help_text='JSON с выделенными фрагментами и замечаниями')

    # Метаданные
    meta_title = models.CharField('Meta Title', max_length=60, blank=True)
    meta_description = models.CharField('Meta Description', max_length=160, blank=True)
    meta_keywords = models.CharField('Ключевые слова', max_length=255, blank=True)

    # Связи
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Автор', related_name='articles')
    categories = models.ManyToManyField(Category, verbose_name='Категории', blank=True, related_name='articles')
    tags = TaggableManager(verbose_name='Теги', blank=True)

    # Статус и даты
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    published_at = models.DateTimeField('Опубликовано', null=True, blank=True)

    # Модерация
    moderation_notes = models.TextField('Заметки модератора', blank=True)
    moderated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='moderated_articles', verbose_name='Модератор')
    moderated_at = models.DateTimeField('Время модерации', null=True, blank=True)

    # Статистика
    views_count = models.PositiveIntegerField('Просмотры', default=0)
    # Хештеги (используем taggit)
    tags = TaggableManager(
        verbose_name='Хештеги',
        blank=True,
        help_text='Введите хештеги через запятую. Например: #ведьмак #монстры #магия'
    )
    class Meta:
        verbose_name = 'Статья'
        verbose_name_plural = 'Статьи'
        ordering = ['-created_at']
        permissions = [
            ("can_moderate", "Может модерировать статьи"),
            ("can_edit_content", "Может редактировать контент"),
            ("can_manage_categories", "Может управлять категориями"),
        ]

    def can_delete(self, user=None):
        """Проверяет, может ли пользователь удалить статью"""
        if user is None:
            return False

        # Автор может удалять свои статьи в определенных статусах
        if user == self.author and self.status in ['draft', 'rejected']:
            return True

        # Модераторы и администраторы могут удалять любые статьи
        if (user.is_staff or
                user.groups.filter(name__in=['Модератор', 'Администратор']).exists()):
            return True

        return False

    def can_edit(self, user):
        """Проверяет, может ли пользователь редактировать статью"""
        if not user.is_authenticated:
            return False

        # Автор может редактировать свои статьи в определенных статусах
        if user == self.author and self.status in ['draft', 'rejected', 'needs_correction', 'author_review']:
            return True

        # Редакторы и модераторы могут редактировать
        if (user.is_staff or
                user.groups.filter(name__in=['Редактор', 'Модератор', 'Администратор']).exists()):
            return True

        return False

    def can_accept_revisions(self, user):
        """Проверяет, может ли пользователь принимать/отклонять правки редактора"""
        if not user.is_authenticated:
            return False

        # Только автор может принимать/отклонять правки в статусе author_review
        return (user == self.author and self.status == 'author_review')

    def accept_editor_revisions(self):
        """Принимает правки редактора и публикует статью"""
        if self.status == 'author_review':
            self.status = 'published'
            self.published_at = timezone.now()
            self.author_notes = 'Исправления редактора приняты'
            self.save()

    def reject_editor_revisions(self, author_notes=''):
        """Отклоняет правки редактора и возвращает в черновики"""
        if self.status == 'author_review':
            self.status = 'draft'
            self.author_notes = author_notes
            self.save()

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('wiki:article_detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if not self.meta_title:
            self.meta_title = self.title[:60]
        if not self.meta_description and self.excerpt:
            self.meta_description = self.excerpt[:160]
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def increment_views(self):
        self.views_count += 1
        self.save(update_fields=['views_count'])

    # Методы для лайков
    def get_likes_count(self):
        """Возвращает количество лайков статьи"""
        return self.likes.count()

    def is_liked_by_user(self, user):
        """Проверяет, лайкнул ли пользователь статью"""
        if not user.is_authenticated:
            return False
        return self.likes.filter(user=user).exists()

    def toggle_like(self, user):
        """Добавляет или убирает лайк"""
        if not user.is_authenticated:
            return False

        like, created = ArticleLike.objects.get_or_create(
            user=user,
            article=self
        )

        if not created:
            like.delete()
            return False  # Лайк убран
        return True  # Лайк добавлен

    # Новые методы для модерации
    def get_status_display_with_icon(self):
        """Возвращает статус с иконкой"""
        icons = {
            'draft': '📝',
            'review': '⏳',
            'needs_correction': '✏️',
            'editor_review': '📝',
            'author_review': '📋',
            'published': '✅',
            'rejected': '❌'
        }
        return f"{icons.get(self.status, '📄')} {self.get_status_display()}"

    def can_be_edited_by_author(self):
        """Может ли автор редактировать статью в текущем статусе"""
        return self.status in ['draft', 'rejected', 'needs_correction']

    def is_awaiting_author_review(self):
        """Ожидает ли статья согласования автора"""
        return self.status == 'author_review'

    def get_moderation_comments_count(self):
        """Количество непросмотренных комментариев модерации"""
        return self.moderation_comments.filter(resolved=False).count()

    # Методы для проверки прав доступа
    def can_edit(self, user):
        """Проверяет, может ли пользователь редактировать статью"""
        if not user.is_authenticated:
            return False

        # Автор может редактировать свои статьи в определенных статусах
        if user == self.author and self.status in ['draft', 'rejected', 'needs_correction']:
            return True

        # Редакторы и модераторы могут редактировать
        if (user.is_staff or
                user.groups.filter(name__in=['Редактор', 'Модератор', 'Администратор']).exists()):
            return True

        return False

    def can_moderate(self, user):
        """Проверяет, может ли пользователь модерировать статью"""
        if not user.is_authenticated:
            return False

        return (user.is_staff or
                user.groups.filter(name__in=['Модератор', 'Администратор']).exists())

    def submit_for_moderation(self):
        """Отправляет статью на модерацию"""
        if self.status == 'draft':
            self.status = 'review'
            self.save()
            return True
        return False

    def can_submit_for_moderation(self, user):
        """Проверяет, может ли пользователь отправить статью на модерацию"""
        if not user.is_authenticated:
            return False
        return (user == self.author and self.status == 'draft')


# models.py - ОБНОВИТЬ модель ModerationComment
class ModerationComment(models.Model):
    """Комментарии модератора к конкретным фрагментам текста"""
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='moderation_comments')
    moderator = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Модератор')

    # Основные поля для выделения текста
    highlighted_text = models.TextField('Выделенный текст')
    comment = models.TextField('Замечание')

    # Позиции в тексте
    start_position = models.IntegerField('Начальная позиция', default=0)
    end_position = models.IntegerField('Конечная позиция', default=0)

    # Дополнительные поля для лучшего UX
    selection_context = models.TextField('Контекст выделения', blank=True,
                                         help_text='Текст вокруг выделенного фрагмента')
    severity = models.CharField('Важность', max_length=20,
                                choices=[
                                    ('low', 'Низкая'),
                                    ('medium', 'Средняя'),
                                    ('high', 'Высокая'),
                                    ('critical', 'Критическая')
                                ], default='medium')

    # Статус комментария
    STATUS_CHOICES = [
        ('open', 'Открыто'),
        ('in_progress', 'В работе'),
        ('resolved', 'Исправлено'),
        ('wont_fix', 'Не будет исправлено'),
    ]
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='open')

    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    resolved_at = models.DateTimeField('Время исправления', null=True, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='resolved_comments', verbose_name='Исправил')

    class Meta:
        verbose_name = 'Комментарий модератора'
        verbose_name_plural = 'Комментарии модераторов'
        ordering = ['-created_at']

    def __str__(self):
        return f'Комментарий к статье "{self.article.title}"'

    def get_severity_color(self):
        """Возвращает цвет для важности"""
        if self.severity == 'low':
            return '#6b7280'
        elif self.severity == 'medium':
            return '#f59e0b'
        elif self.severity == 'high':
            return '#ef4444'
        elif self.severity == 'critical':
            return '#dc2626'
        return '#f59e0b'

    def get_severity_display(self):
        """Возвращает название важности"""
        if self.severity == 'low':
            return 'Низкая'
        elif self.severity == 'medium':
            return 'Средняя'
        elif self.severity == 'high':
            return 'Высокая'
        elif self.severity == 'critical':
            return 'Критическая'
        return 'Средняя'

    def mark_as_resolved(self, user):
        """Пометить как исправленный"""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.save()


class ArticleMedia(models.Model):
    """Медиафайлы для статей"""
    MEDIA_TYPES = [
        ('image', 'Изображение'),
        ('video', 'Видео'),
        ('audio', 'Аудио'),
        ('document', 'Документ'),
    ]

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='media_files', verbose_name='Статья')
    file = models.FileField('Файл', upload_to='article_media/')
    file_type = models.CharField('Тип файла', max_length=20, choices=MEDIA_TYPES)
    title = models.CharField('Название', max_length=200, blank=True)
    description = models.TextField('Описание', blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Загрузил')
    uploaded_at = models.DateTimeField('Загружено', auto_now_add=True)
    display_order = models.IntegerField('Порядок отображения', default=0)

    class Meta:
        verbose_name = 'Медиафайл статьи'
        verbose_name_plural = 'Медиафайлы статей'
        ordering = ['display_order', '-uploaded_at']

    def __str__(self):
        return self.title or f'Медиа {self.id}'

    def get_file_url(self):
        return self.file.url

    def is_image(self):
        return self.file_type == 'image'

    def is_video(self):
        return self.file_type == 'video'

    def get_file_extension(self):
        """Возвращает расширение файла в нижнем регистре"""
        if self.file and hasattr(self.file, 'name'):
            return self.file.name.split('.')[-1].lower() if '.' in self.file.name else ''
        return ''
    def get_clean_filename(self):
        """Возвращает чистое имя файла без пути"""
        if self.file and hasattr(self.file, 'name'):
            return self.file.name.split('/')[-1]
        return self.title or f'Файл {self.id}'

class ArticleRevision(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='revisions', verbose_name='Статья')
    title = models.CharField('Заголовок', max_length=200)
    content = CKEditor5Field('Содержание', config_name='default')
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Автор')
    comment = models.CharField('Комментарий к изменению', max_length=255, blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Версия статьи'
        verbose_name_plural = 'Версии статей'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.article.title} - {self.created_at.strftime("%d.%m.%Y %H:%M")}'


class Comment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='comments', verbose_name='Статья')
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Автор')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                               verbose_name='Родительский комментарий', related_name='replies')
    content = models.TextField('Комментарий')
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    is_approved = models.BooleanField('Одобрен', default=True)

    class Meta:
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'
        ordering = ['created_at']

    def __str__(self):
        return f'Комментарий от {self.author.username} к {self.article.title}'


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField('Аватар', upload_to='avatars/', blank=True, null=True)
    bio = models.TextField('О себе', blank=True)

    # Соцсети вместо веб-сайта
    telegram = models.URLField('Telegram', blank=True, max_length=255)
    vk = models.URLField('VK', blank=True, max_length=255)
    youtube = models.URLField('YouTube', blank=True, max_length=255)
    discord = models.CharField('Discord', blank=True, max_length=100)

    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'

    def get_safe_email_display(self, requesting_user):
        """Безопасное отображение email (только для владельца и админов)"""
        if requesting_user == self.user or requesting_user.is_staff:
            return self.user.email
        else:
            # Показываем только часть email для безопасности
            if self.user.email:
                username, domain = self.user.email.split('@')
                hidden_username = username[:2] + '***' + username[-1:]
                return f"{hidden_username}@{domain}"
            return "Скрыто"

    def __str__(self):
        return f'Профиль пользователя {self.user.username}'

    def has_social_links(self):
        """Проверяет, есть ли у пользователя соцсети"""
        return bool(self.telegram or self.vk or self.youtube or self.discord)

    def get_telegram_username(self):
        """Извлекает username из ссылки Telegram"""
        if self.telegram:
            if 't.me/' in self.telegram:
                return self.telegram.split('t.me/')[-1]
            elif '@' in self.telegram:
                return self.telegram.replace('@', '')
        return None

    def get_vk_username(self):
        """Извлекает username из ссылки VK"""
        if self.vk:
            if 'vk.com/' in self.vk:
                return self.vk.split('vk.com/')[-1]
        return None

    def save(self, *args, **kwargs):
        if self.avatar:
            self.resize_avatar()
        super().save(*args, **kwargs)

    def resize_avatar(self):
        """Изменяет размер аватара до 300x300 пикселей"""
        try:
            from PIL import Image
            from io import BytesIO
            from django.core.files.base import ContentFile
            import os

            # Открываем изображение
            img = Image.open(self.avatar)

            # Конвертируем в RGB если нужно
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            # Получаем текущий размер
            width, height = img.size

            # Ограничиваем максимальный размер
            max_size = 300
            if width > max_size or height > max_size:
                # Вычисляем новые размеры сохраняя пропорции
                if width > height:
                    new_width = max_size
                    new_height = int(height * max_size / width)
                else:
                    new_height = max_size
                    new_width = int(width * max_size / height)

                # Изменяем размер
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Сохраняем обратно в поле avatar
            thumb_io = BytesIO()
            img.save(thumb_io, format='JPEG', quality=85, optimize=True)

            # Получаем имя файла
            avatar_name = self.avatar.name
            if not avatar_name.startswith('avatars/'):
                file_ext = os.path.splitext(avatar_name)[1] or '.jpg'
                avatar_name = f"avatars/user_{self.user.id}/avatar{file_ext}"

            # Сохраняем измененное изображение
            self.avatar.save(
                avatar_name,
                ContentFile(thumb_io.getvalue()),
                save=False
            )

        except Exception as e:
            # В случае ошибки просто сохраняем без изменений
            print(f"Ошибка при обработке аватара: {e}")
            pass

    def delete_old_avatar(self):
        """Удаляет старый аватар при загрузке нового"""
        try:
            import os
            from django.core.files.storage import default_storage

            if self.avatar:
                # Получаем старый профиль если он существует
                old_profile = UserProfile.objects.filter(user=self.user).first()
                if old_profile and old_profile.avatar and old_profile.avatar != self.avatar:
                    if default_storage.exists(old_profile.avatar.name):
                        default_storage.delete(old_profile.avatar.name)
        except Exception as e:
            print(f"Ошибка при удалении старого аватара: {e}")


class MediaLibrary(models.Model):
    title = models.CharField('Название', max_length=200)
    file = models.FileField('Файл', upload_to='media_library/')
    file_type = models.CharField('Тип файла', max_length=50)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Загрузил')
    uploaded_at = models.DateTimeField('Загружено', auto_now_add=True)

    class Meta:
        verbose_name = 'Медиафайл'
        verbose_name_plural = 'Медиатека'
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.title


class ArticleLike(models.Model):
    """Модель для лайков статей"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    article = models.ForeignKey(Article, on_delete=models.CASCADE, verbose_name='Статья', related_name='likes')
    created_at = models.DateTimeField('Время лайка', auto_now_add=True)

    class Meta:
        verbose_name = 'Лайк статьи'
        verbose_name_plural = 'Лайки статей'
        unique_together = ['user', 'article']  # Один лайк на статью от пользователя
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} лайкнул {self.article.title}'


class SearchQuery(models.Model):
    """Модель для хранения поисковых запросов"""
    query = models.CharField('Запрос', max_length=255)
    count = models.PositiveIntegerField('Количество', default=1)
    last_searched = models.DateTimeField('Последний поиск', auto_now=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Поисковый запрос'
        verbose_name_plural = 'Поисковые запросы'
        ordering = ['-count', '-last_searched']

    def __str__(self):
        return f'{self.query} ({self.count})'

    def increment(self):
        """Увеличивает счетчик запроса"""
        self.count += 1
        self.save()


class Message(models.Model):
    """Модель для личных сообщений между пользователями"""
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        verbose_name='Отправитель'
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_messages',
        verbose_name='Получатель'
    )
    subject = models.CharField('Тема', max_length=200)
    content = models.TextField('Сообщение')

    # Статус сообщения
    is_read = models.BooleanField('Прочитано', default=False)
    sender_deleted = models.BooleanField('Удалено отправителем', default=False)
    recipient_deleted = models.BooleanField('Удалено получателем', default=False)

    created_at = models.DateTimeField('Создано', auto_now_add=True)
    read_at = models.DateTimeField('Прочитано', null=True, blank=True)

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['-created_at']
        permissions = [
            ("can_message_users", "Может отправлять сообщения пользователям"),
        ]

    def __str__(self):
        return f'{self.sender.username} → {self.recipient.username}: {self.subject}'

    def mark_as_read(self):
        """Пометить сообщение как прочитанное"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    def can_view(self, user):
        """Проверяет, может ли пользователь просматривать сообщение"""
        return user in [self.sender, self.recipient]

    def can_delete(self, user):
        """Проверяет, может ли пользователь удалить сообщение"""
        return user in [self.sender, self.recipient]

class EmailVerification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)  # ДОБАВЬТЕ null=True, blank=True
    email = models.EmailField()
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    purpose = models.CharField(max_length=20, choices=[
        ('registration', 'Регистрация'),
        ('password_reset', 'Восстановление пароля'),
    ])

    def is_valid(self):
        """Проверяет, действителен ли код (15 минут)"""
        return (timezone.now() - self.created_at) < timedelta(minutes=15) and not self.is_used

    def generate_code(self):
        """Генерирует 6-значный цифровой код"""
        return ''.join(random.choices(string.digits, k=6))

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.email} - {self.code}"

class TelegramVerification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    telegram_id = models.BigIntegerField(unique=True)
    telegram_username = models.CharField(max_length=32, blank=True)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        return (timezone.now() - self.created_at) < timedelta(minutes=15) and not self.is_used

    def generate_code(self):
        return ''.join(random.choices(string.digits, k=6))

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_code()
        super().save(*args, **kwargs)


# models.py - обновленная модель TelegramUser
class TelegramUser(models.Model):
    """Модель для связи пользователя с Telegram аккаунтом"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='telegram_account'
    )
    telegram_id = models.BigIntegerField(unique=True, verbose_name='ID в Telegram')
    telegram_username = models.CharField(
        max_length=32,
        blank=True,
        verbose_name='Username в Telegram'
    )
    first_name = models.CharField(max_length=64, blank=True, verbose_name='Имя в Telegram')
    last_name = models.CharField(max_length=64, blank=True, verbose_name='Фамилия в Telegram')
    photo_url = models.URLField(blank=True, verbose_name='Фото профиля')
    auth_date = models.DateTimeField(
        verbose_name='Дата авторизации',
        default=timezone.now  # ДОБАВЛЕНО default значение
    )
    hash = models.CharField(
        max_length=255,
        verbose_name='Хеш авторизации',
        blank=True,  # ДОБАВЛЕНО blank=True для существующих записей
        default=''   # ДОБАВЛЕНО default значение
    )
    is_verified = models.BooleanField(default=True, verbose_name='Подтвержден')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата привязки')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        verbose_name = 'Telegram пользователь'
        verbose_name_plural = 'Telegram пользователи'

    def __str__(self):
        return f"@{self.telegram_username}" if self.telegram_username else f"ID: {self.telegram_id}"

    def get_full_name(self):
        """Возвращает полное имя"""
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return ' '.join(parts) if parts else 'Пользователь Telegram'


class AuthCode(models.Model):
    """Модель для хранения кодов авторизации Telegram"""
    code = models.CharField('Код', max_length=6, unique=True)
    telegram_id = models.BigIntegerField('ID Telegram')
    telegram_username = models.CharField('Username Telegram', max_length=32, blank=True)
    first_name = models.CharField('Имя', max_length=64, blank=True)

    # Статус использования
    is_used = models.BooleanField('Использован', default=False)
    used_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True,
                                verbose_name='Использован пользователем')
    used_at = models.DateTimeField('Время использования', null=True, blank=True)

    # Срок действия
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    expires_at = models.FloatField('Истекает')  # Unix timestamp

    class Meta:
        verbose_name = 'Код авторизации'
        verbose_name_plural = 'Коды авторизации'
        ordering = ['-created_at']

    def __str__(self):
        return f"Код {self.code} для {self.telegram_username or self.telegram_id}"

    def is_expired(self):
        import time
        return time.time() > self.expires_at