from django.db import migrations

# Убираем из описаний релизов то, чего в системе больше нет (Ctrl+K, «стиль Telegram Web»).
FIXES = {
    '1.1.0': [
        ('Полный редизайн в стиле Telegram Web с новым сайдбаром, шапкой и карточками',
         'Новый интерфейс: боковая панель, шапка и карточки разделов'),
        ('Тёмная тема с плавным переключателем (сохраняется в localStorage)',
         'Тёмная тема; выбор темы запоминается в браузере'),
        ('колокольчик с red dot', 'колокольчик с отметкой о новых'),
    ],
    '1.2.0': [
        (' Ctrl+K или Cmd+K переводит фокус в поиск.', ''),
    ],
}


def fix(apps, schema_editor):
    Changelog = apps.get_model('knowledge', 'Changelog')
    for version, pairs in FIXES.items():
        for release in Changelog.objects.filter(version=version):
            text = release.description
            for old, new in pairs:
                text = text.replace(old, new)
            if text != release.description:
                release.description = text
                release.save(update_fields=['description'])


class Migration(migrations.Migration):
    dependencies = [('knowledge', '0010_root_section_icons')]
    operations = [migrations.RunPython(fix, migrations.RunPython.noop)]
