from django.apps import AppConfig
from django.db.models.signals import post_migrate

def run_seed_data(sender, **kwargs):
    """Автоматически запускает seed_data после миграций"""
    from django.core.management import call_command
    try:
        from .models import Article, Section
        if not Article.objects.exists() and not Section.objects.exists():
            call_command('seed_data')
    except Exception:
        pass  # Игнорируем ошибки при первом запуске (таблицы ещё нет)

class KnowledgeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'knowledge'

    def ready(self):
        post_migrate.connect(run_seed_data, sender=self)