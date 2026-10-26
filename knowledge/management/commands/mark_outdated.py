from django.core.management.base import BaseCommand

from knowledge.models import Article


class Command(BaseCommand):
    help = 'Помечает устаревшими статьи, не подтверждённые больше 90 дней (регламент 5.4); запускать ежедневно'

    def handle(self, *args, **options):
        self.stdout.write(f'Помечено устаревшими: {Article.mark_expired()}')
