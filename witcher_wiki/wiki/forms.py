from django import forms
from django.db.models import Q

from .models import Article, Comment, Category
from django_ckeditor_5.widgets import CKEditor5Widget
from django import forms
from .models import Article, Comment, Category, ArticleMedia


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['title', 'content', 'excerpt', 'categories', 'tags', 'status', 'featured_image']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'excerpt': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'featured_image': forms.FileInput(attrs={'class': 'form-control'}),
        }


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
class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['title', 'slug', 'excerpt', 'content', 'featured_image', 'categories', 'tags', 'status']
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
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Теги через запятую: ведьмак, геральт, монстры'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
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
