from django.db import migrations

# Краткие описания корневых разделов для карточек на главной странице.
# Заполняются только пустые описания, чтобы не затереть уже написанные вручную.
DESCRIPTIONS = {
    'О системе': 'Назначение системы Planning Force, её модули, глоссарий и сведения о разработчике',
    'Планирование спроса': 'Модуль Demand: прогноз спроса, табличная форма, график, корректировки, импорт и экспорт',
    'Промо планирование': 'Календари промо, промо кампании, простые акции, товары и оптимизатор промо (TPO)',
    'Управление остатками': 'Модуль Replenishment: схемы управления запасами, заказы, статусы и кванты поставки',
    'Администрирование': 'Роли и доступы, статусные модели и согласования, алерты и общие механики интерфейса',
}


def fill(apps, schema_editor):
    Section = apps.get_model('knowledge', 'Section')
    for name, text in DESCRIPTIONS.items():
        Section.objects.filter(name=name, parent__isnull=True, description='').update(description=text)


class Migration(migrations.Migration):
    dependencies = [('knowledge', '0008_collection_role_project')]
    operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
