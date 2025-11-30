from django.contrib.auth.models import User
from django.db.models import Q

from django_ckeditor_5.widgets import CKEditor5Widget
from .models import Article, Comment, Category, ArticleMedia
from .models import UserProfile
from django.core.validators import FileExtensionValidator
from .models import Message
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import re
from .models import EmailVerification, TelegramVerification
from django.core.mail import send_mail
from django.conf import settings
from django import forms
from .models import BackupLog


class ArticleForm(forms.ModelForm):
    tags_input = forms.CharField(
        required=False,
        label='Хештеги',
        help_text='Введите хештеги через запятую. Например: ведьмак, монстры, магия',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ведьмак, монстры, магия...'
        })
    )

    class Meta:
        model = Article
        fields = ['title', 'slug', 'excerpt', 'content', 'featured_image', 'categories', 'status']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите заголовок статьи...'
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'url-адрес-статьи'
            }),
            'excerpt': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Краткое описание статьи...'
            }),
            'content': CKEditor5Widget(attrs={
                'class': 'django_ckeditor_5'
            }, config_name='extends'),
            'featured_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'categories': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем slug необязательным для пользователя
        self.fields['slug'].required = False

        # Если редактируем существующую статью, показываем текущие теги
        if self.instance and self.instance.pk:
            self.fields['tags_input'].initial = ', '.join(tag.name for tag in self.instance.tags.all())

        self.fields['slug'].help_text = 'Оставьте пустым для автоматической генерации'
        self.fields['excerpt'].help_text = 'Краткое описание для поисковых систем'
        self.fields['content'].help_text = 'Используйте редактор для форматирования текста'

    def save(self, commit=True):
        article = super().save(commit=False)

        if commit:
            article.save()
            self.save_m2m()

            # Сохраняем хештеги
            tags_input = self.cleaned_data.get('tags_input', '')
            if tags_input:
                # Очищаем и форматируем теги
                tags_list = [tag.strip().lower() for tag in tags_input.split(',') if tag.strip()]
                article.tags.set(*tags_list)

        return article

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Оставьте ваш комментарий...'
            }),
        }


class SearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Поиск по статьям...'
        })
    )
    category = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'parent', 'is_featured', 'display_order', 'icon']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'parent': forms.Select(attrs={'class': 'form-control'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '⚔️'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Исключаем текущую категорию и ее потомков из выбора родителя
        if self.instance and self.instance.pk:
            self.fields['parent'].queryset = Category.objects.exclude(
                Q(id=self.instance.pk) |
                Q(children__id=self.instance.pk)
            )
        else:
            self.fields['parent'].queryset = Category.objects.all()


class ArticleMediaForm(forms.ModelForm):
    class Meta:
        model = ArticleMedia
        fields = ['file', 'title', 'description', 'file_type', 'display_order']
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'file_type': forms.Select(attrs={'class': 'form-control'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем slug необязательным для пользователя
        self.fields['slug'].required = False
        # Добавляем help_text
        self.fields['slug'].help_text = 'Оставьте пустым для автоматической генерации'
        self.fields['tags'].help_text = 'Введите теги через запятую'
        self.fields['excerpt'].help_text = 'Краткое описание для поисковых систем'
        self.fields['content'].help_text = 'Используйте редактор для форматирования текста'

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        title = self.cleaned_data.get('title')

        # Если slug пустой, генерируем его из заголовка
        if not slug and title:
            from django.utils.text import slugify
            import re
            # Транслитерация для русских символов
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

        return slug


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': CKEditor5Widget(attrs={
                'class': 'django_ckeditor_5'
            }, config_name='comment')
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['content'].label = 'Комментарий'
        self.fields['content'].help_text = 'Поделитесь своими мыслями о статье'


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'slug', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название категории'
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'url-адрес-категории'
            }),
            'description': CKEditor5Widget(attrs={
                'class': 'django_ckeditor_5'
            }, config_name='simple')
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['description'].required = False
        self.fields['slug'].help_text = 'Оставьте пустым для автоматической генерации'
        self.fields['description'].help_text = 'Описание категории с возможностью форматирования'

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        name = self.cleaned_data.get('name')

        if not slug and name:
            from django.utils.text import slugify
            # Простая транслитерация
            translit_dict = {
                'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
                'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
                'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
                'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
                'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
            }

            name_lower = name.lower()
            for ru, en in translit_dict.items():
                name_lower = name_lower.replace(ru, en)

            slug = slugify(name_lower)

        return slug


class SearchForm(forms.Form):
    query = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Поиск по статьям...',
            'autocomplete': 'off'
        }),
        label='Поиск'
    )

    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        empty_label='Все категории',
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        label='Категория'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['query'].help_text = 'Введите ключевые слова для поиска'


# Дополнительная форма для быстрого создания статьи
class QuickArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['title', 'content', 'categories']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Заголовок статьи...'
            }),
            'content': CKEditor5Widget(attrs={
                'class': 'django_ckeditor_5'
            }, config_name='default'),
            'categories': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].help_text = 'Введите заголовок статьи'
        self.fields['content'].help_text = 'Основное содержание статьи'
        self.fields['categories'].help_text = 'Выберите подходящие категории'

    def save(self, commit=True):
        article = super().save(commit=False)
        if not article.slug:
            from django.utils.text import slugify
            # Автогенерация slug из заголовка
            translit_dict = {
                'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
                'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
                'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
                'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
                'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
            }

            title_lower = article.title.lower()
            for ru, en in translit_dict.items():
                title_lower = title_lower.replace(ru, en)

            article.slug = slugify(title_lower)

        if not article.excerpt:
            # Автогенерация excerpt из content (первые 150 символов)
            from django.utils.html import strip_tags
            content_text = strip_tags(article.content)
            article.excerpt = content_text[:150] + '...' if len(content_text) > 150 else content_text

        if commit:
            article.save()
            self.save_m2m()
        return article


class ProfileUpdateForm(forms.ModelForm):
    avatar = forms.ImageField(
        required=False,
        label='Аватар',
        help_text='Рекомендуемый размер: 300x300 пикселей. Максимальный размер: 2MB. Разрешены: JPG, PNG, GIF',
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif'])],
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        })
    )

    first_name = forms.CharField(
        required=False,
        label='Имя',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ваше имя'
        })
    )

    last_name = forms.CharField(
        required=False,
        label='Фамилия',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ваша фамилия'
        })
    )

    email = forms.EmailField(
        required=True,
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your@email.com'
        })
    )

    bio = forms.CharField(
        required=False,
        label='О себе',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Расскажите о себе...'
        })
    )

    # Поля для соцсетей
    telegram = forms.URLField(
        required=False,
        label='Telegram',
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://t.me/username'
        })
    )

    vk = forms.URLField(
        required=False,
        label='VK',
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://vk.com/username'
        })
    )

    youtube = forms.URLField(
        required=False,
        label='YouTube',
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://youtube.com/c/username'
        })
    )

    discord = forms.CharField(
        required=False,
        label='Discord',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'username#1234'
        })
    )

    class Meta:
        model = UserProfile
        fields = ['avatar', 'bio', 'telegram', 'vk', 'youtube', 'discord']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)

        if self.user:
            if 'avatar' in self.changed_data:
                profile.delete_old_avatar()

            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.email = self.cleaned_data['email']
            self.user.save()

        if commit:
            profile.save()

        return profile


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['recipient', 'subject', 'content']
        widgets = {
            'recipient': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'Выберите получателя'
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Тема сообщения'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Текст сообщения...'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.sender = kwargs.pop('sender', None)
        super().__init__(*args, **kwargs)

        # Фильтруем получателей - нельзя отправлять себе
        if self.sender:
            self.fields['recipient'].queryset = User.objects.exclude(id=self.sender.id)

        self.fields['recipient'].label = 'Получатель'
        self.fields['subject'].label = 'Тема'
        self.fields['content'].label = 'Сообщение'


# В forms.py ДОБАВЬТЕ:
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import re

# В forms.py ДОБАВЬТЕ:
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import re


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your@email.com'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('Пользователь с таким email уже существует.')
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        # Проверка на допустимые символы
        if not re.match(r'^[\w.@+-]+\Z', username):
            raise ValidationError('Имя пользователя содержит недопустимые символы.')
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user

class QuickMessageForm(forms.Form):
    """Форма для быстрой отправки сообщения"""
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Введите ваше сообщение...'
        }),
        label='Сообщение'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['content'].help_text = 'Максимум 1000 символов'


class EmailVerificationForm(forms.Form):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your@email.com'
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('Пользователь с таким email уже существует.')
        return email

    def send_verification_code(self, purpose='registration'):
        email = self.cleaned_data['email']
        # Деактивируем старые коды для этого email
        EmailVerification.objects.filter(email=email, purpose=purpose).update(is_used=True)

        # Создаем новый код
        verification = EmailVerification.objects.create(
            email=email,
            purpose=purpose
        )

        # Отправляем email
        subject = 'Код подтверждения для регистрации' if purpose == 'registration' else 'Код восстановления пароля'
        message = f'''
        Ваш код подтверждения: {verification.code}

        Код действителен в течение 15 минут.

        Если вы не запрашивали этот код, проигнорируйте это сообщение.
        '''

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )

        return verification


class CodeVerificationForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '123456',
            'maxlength': '6'
        })
    )

    def __init__(self, *args, **kwargs):
        self.email = kwargs.pop('email', None)
        self.purpose = kwargs.pop('purpose', 'registration')
        super().__init__(*args, **kwargs)

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if self.email:
            try:
                verification = EmailVerification.objects.get(
                    email=self.email,
                    code=code,
                    purpose=self.purpose,
                    is_used=False
                )
                if not verification.is_valid():
                    raise ValidationError('Код устарел или недействителен.')
                self.verification = verification
            except EmailVerification.DoesNotExist:
                raise ValidationError('Неверный код подтверждения.')
        return code


class CompleteRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.HiddenInput())
    code = forms.CharField(max_length=6, widget=forms.HiddenInput())

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError('Пользователь с таким именем уже существует.')
        return username


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your@email.com'
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not User.objects.filter(email=email).exists():
            raise ValidationError('Пользователь с таким email не найден.')
        return email


class PasswordResetForm(forms.Form):
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        min_length=8
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    code = forms.CharField(max_length=6, widget=forms.HiddenInput())

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')

        if password1 and password2 and password1 != password2:
            raise ValidationError('Пароли не совпадают.')

        return cleaned_data


class TelegramLoginForm(forms.Form):
    """Форма для входа через Telegram"""
    telegram_init_data = forms.CharField(
        widget=forms.HiddenInput(attrs={'id': 'telegram-init-data'})
    )

    def clean_telegram_init_data(self):
        data = self.cleaned_data.get('telegram_init_data')
        if not data:
            raise ValidationError('Данные Telegram не получены')
        return data


class TelegramConnectForm(forms.Form):
    """Форма для привязки Telegram к существующему аккаунту"""
    telegram_init_data = forms.CharField(
        widget=forms.HiddenInput(attrs={'id': 'telegram-connect-data'})
    )


class BackupForm(forms.ModelForm):
    """Форма для создания бэкапа"""

    BACKUP_CHOICES = [
        ('all', '🔮 Все логи (полный бэкап)'),
        ('selected', '🎯 Выбранные записи (вручную)'),
        ('period', '📅 За период (по дате)'),
    ]

    FORMAT_CHOICES = [
        ('json', '📄 JSON (рекомендуется)'),
        ('pdf', '📊 PDF (для печати)'),
    ]

    backup_type = forms.ChoiceField(
        choices=BACKUP_CHOICES,
        widget=forms.RadioSelect,
        label='Тип бэкапа'
    )

    format = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        widget=forms.RadioSelect,
        label='Формат экспорта'
    )

    start_date = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label='С даты'
    )

    end_date = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label='По дату'
    )

    selected_logs = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label='Выбранные логи'
    )

    class Meta:
        model = BackupLog
        fields = ['name', 'backup_type', 'format', 'start_date', 'end_date', 'selected_logs']

    def clean(self):
        cleaned_data = super().clean()
        backup_type = cleaned_data.get('backup_type')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        selected_logs = cleaned_data.get('selected_logs')

        if backup_type == 'period':
            if not start_date or not end_date:
                raise forms.ValidationError('Для бэкапа за период необходимо указать начальную и конечную дату.')
            if start_date > end_date:
                raise forms.ValidationError('Начальная дата не может быть больше конечной.')

        elif backup_type == 'selected':
            if not selected_logs:
                raise forms.ValidationError('Для выборочного бэкапа необходимо выбрать хотя бы одну запись.')

        return cleaned_data