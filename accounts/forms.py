from django import forms
from django.contrib.auth.models import User
from .models import UserProfile


class UserProfileForm(forms.ModelForm):
    """Форма редактирования профиля"""
    class Meta:
        model = UserProfile
        fields = ['avatar', 'position', 'bio']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Расскажите о себе...'}),
        }


class UserEmailForm(forms.ModelForm):
    """Форма редактирования email пользователя"""
    class Meta:
        model = User
        fields = ['email']
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'Email (необязательно)'}),
        }
