from django.db import migrations, models


def set_levels(apps, schema_editor):
    UserProfile = apps.get_model('accounts', 'UserProfile')
    for profile in UserProfile.objects.select_related('user'):
        profile.access_level = 'admin' if profile.user.is_superuser else 'editor'
        profile.save(update_fields=['access_level'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_profile_position'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='access_level',
            field=models.CharField(choices=[('reader', 'Читатель'), ('editor', 'Редактор'), ('admin', 'Администратор')], default='editor', max_length=10, verbose_name='Уровень доступа'),
        ),
        migrations.RunPython(set_levels, migrations.RunPython.noop),
    ]
