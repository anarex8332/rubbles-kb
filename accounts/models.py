from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    """Профиль пользователя"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField('Фото', upload_to='avatars/', blank=True, null=True)
    # Онтология: «участник и роль» — роль участника это его должность в компании
    position = models.CharField('Должность (роль)', max_length=150, blank=True)
    ACCESS_CHOICES = [
        ('reader', 'Читатель'),
        ('editor', 'Редактор'),
        ('admin', 'Администратор'),
    ]
    # Уровень доступа участника (раздел 2.7 ВКР); на прототипе у всех «Редактор»
    access_level = models.CharField('Уровень доступа', max_length=10, choices=ACCESS_CHOICES, default='editor')
    bio = models.TextField('О себе', max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'

    def __str__(self):
        return f'Профиль {self.user.username}'

    @property
    def can_edit(self):
        return self.access_level != 'reader'


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Автоматическое создание профиля при регистрации пользователя"""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Автоматическое сохранение профиля"""
    if hasattr(instance, 'profile'):
        instance.profile.save()