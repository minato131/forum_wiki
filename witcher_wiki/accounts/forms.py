from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate
from wiki.logging_utils import ActionLogger


class CustomAuthenticationForm(AuthenticationForm):
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                # Логирование неудачной попытки входа
                ActionLogger.log_action(
                    request=self.request,
                    action_type='login_failed',
                    description=f'Неудачная попытка входа для пользователя {username}',
                    extra_data={
                        'username': username,
                        'ip_address': ActionLogger.get_client_ip(self.request),
                    }
                )
                raise forms.ValidationError(
                    self.error_messages['invalid_login'],
                    code='invalid_login',
                    params={'username': self.username_field.verbose_name},
                )
            else:
                self.confirm_login_allowed(self.user_cache)

                # Логирование успешного входа
                ActionLogger.log_action(
                    request=self.request,
                    action_type='login',
                    description=f'Пользователь {username} вошел в систему',
                    extra_data={
                        'login_method': 'standard_form',
                        'username': username,
                        'ip_address': ActionLogger.get_client_ip(self.request),
                    }
                )

        return self.cleaned_data