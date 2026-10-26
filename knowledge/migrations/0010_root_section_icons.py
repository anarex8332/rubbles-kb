from django.db import migrations

# Своя иконка для каждого корневого раздела (вместо одинаковой папки).
ICONS = {
    'О компании': 'building-2',
    'Планирование спроса': 'trending-up',
    'Промо планирование': 'tag',
    'Управление остатками': 'package',
    'Администрирование': 'settings',
    'О системе': 'info',
}


def fill(apps, schema_editor):
    Section = apps.get_model('knowledge', 'Section')
    for name, icon in ICONS.items():
        Section.objects.filter(name=name, parent__isnull=True).update(icon=icon)


class Migration(migrations.Migration):
    dependencies = [('knowledge', '0009_root_section_descriptions')]
    operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
