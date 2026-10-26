from django.db import migrations


def google_docs_to_bt(apps, schema_editor):
    RelatedLink = apps.get_model('knowledge', 'RelatedLink')
    for host in ('docs.google.com', 'drive.google.com'):
        RelatedLink.objects.filter(from_text=True, link_type='docs',
                                   url__regex=rf'^https?://{host}/').update(link_type='bt')


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge', '0006_relatedlink_from_text'),
    ]

    operations = [
        migrations.RunPython(google_docs_to_bt, migrations.RunPython.noop),
    ]
