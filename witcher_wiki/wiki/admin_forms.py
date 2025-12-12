from django import forms
from django.contrib.auth.models import User
from .models import UserBan, UserWarning


class UserBanForm(forms.ModelForm):
    """Форма для бана пользователя"""

    class Meta:
        model = UserBan
        fields = ['reason', 'duration', 'notes']
        widgets = {
            'reason': forms.Select(attrs={
                'class': 'form-control',
                'style': 'width: 300px;'
            }),
            'duration': forms.Select(attrs={
                'class': 'form-control',
                'style': 'width: 300px;'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Дополнительные детали или пояснения...',
                'style': 'width: 100%; max-width: 500px;'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['reason'].label = 'Причина бана'
        self.fields['duration'].label = 'Длительность бана'
        self.fields['notes'].label = 'Заметки (опционально)'


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