from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone
from django_ckeditor_5.fields import CKEditor5Field
from taggit.managers import TaggableManager


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
        ('published', 'Опубликовано'),
        ('rejected', 'Отклонено'),
        ('archived', 'Архив'),
    ]

    # Сначала все поля модели
    title = models.CharField('Заголовок', max_length=200)
    slug = models.SlugField('URL', unique=True, max_length=200)
    content = CKEditor5Field('Содержание', config_name='extends')
    excerpt = models.TextField('Краткое описание', max_length=500, blank=True)
    featured_image = models.ImageField('Главное изображение', upload_to='articles/', blank=True, null=True)

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

    class Meta:
        verbose_name = 'Статья'
        verbose_name_plural = 'Статьи'
        ordering = ['-created_at']

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

    def can_edit(self, user):
        """Проверяет, может ли пользователь редактировать статью"""
        return (user == self.author or
                user.is_staff or
                user.groups.filter(name__in=['Модератор', 'Администратор']).exists())

    def can_moderate(self, user):
        """Проверяет, может ли пользователь модерировать статью"""
        return (user.is_staff or
                user.groups.filter(name__in=['Модератор', 'Администратор']).exists())

    # МЕТОДЫ ДЛЯ ЛАЙКОВ ДОЛЖНЫ БЫТЬ ПОСЛЕ ВСЕХ ПОЛЕЙ
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
        return self.file.name.split('.')[-1].lower()


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