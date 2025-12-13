from django import forms
from django.contrib.auth.models import User
from .models import UserBan, UserWarning


# Исправленная версия UserBanForm
class UserBanForm(forms.Form):
    REASON_CHOICES = [
        ('spam', 'Спам и реклама'),
        ('abuse', 'Оскорбления и харассмент'),
        ('hate_speech', 'Разжигание ненависти'),
        ('fake_news', 'Распространение ложной информации'),
        ('illegal_content', 'Незаконный контент'),
        ('multiple_violations', 'Множественные нарушения'),
        ('nudity', 'Непристойный контент'),
        ('copyright', 'Нарушение авторских прав'),
        ('impersonation', 'Выдача себя за другого'),
        ('threats', 'Угрозы и запугивание'),
        ('other', 'Другое'),
    ]

    DURATION_CHOICES = [
        ('1h', '1 час'),
        ('12h', '12 часов'),
        ('1d', '1 день'),
        ('3d', '3 дня'),
        ('7d', '7 дней'),
        ('30d', '30 дней'),
        ('permanent', 'Постоянно'),
    ]

    reason = forms.ChoiceField(
        choices=REASON_CHOICES,
        label='Причина бана*',
        widget=forms.Select(attrs={
            'style': 'width: 100%; padding: 12px; background: #1a1a1a; border: 1px solid #D4AF37; border-radius: 5px; color: #e8e8e8;'
        })
    )

    duration = forms.ChoiceField(
        choices=DURATION_CHOICES,
        label='Длительность*',
        widget=forms.Select(attrs={
            'style': 'width: 100%; padding: 12px; background: #1a1a1a; border: 1px solid #D4AF37; border-radius: 5px; color: #e8e8e8;'
        })
    )

    notes = forms.CharField(
        required=False,
        label='Дополнительные заметки',
        widget=forms.Textarea(attrs={
            'rows': 4,
            'style': 'width: 100%; padding: 12px; background: #1a1a1a; border: 1px solid #D4AF37; border-radius: 5px; color: #e8e8e8;',
            'placeholder': 'Внутренние заметки для других модераторов...'
        })
    )

class UserWarningForm(forms.ModelForm):
    """Форма для выдачи предупреждения"""

    class Meta:
        model = UserWarning
        fields = ['severity', 'reason', 'related_content']
        widgets = {
            'severity': forms.Select(attrs={
                'class': 'form-control',
                'style': 'width: 300px;'
            }),
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Подробно опишите причину предупреждения...',
                'style': 'width: 100%; max-width: 500px;'
            }),
            'related_content': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'URL или описание контента...',
                'style': 'width: 100%; max-width: 500px;'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['severity'].label = 'Уровень серьезности'
        self.fields['reason'].label = 'Причина предупреждения'
        self.fields['related_content'].label = 'Связанный контент (опционально)'


class UserSearchForm(forms.Form):
    """Форма поиска пользователей для модерации"""
    username = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите имя пользователя...',
            'style': 'width: 300px;'
        }),
        label='Имя пользователя'
    )

    email = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите email...',
            'style': 'width: 300px;'
        }),
        label='Email'
    )

    has_warnings = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='Только с предупреждениями'
    )

    is_banned = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='Только забаненные'
    )