import zipfile
from datetime import timedelta
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Резервная копия базы и загруженных файлов; копии старше 7 дней удаляются (НФТ-07)'

    def add_arguments(self, parser):
        parser.add_argument('--dir', default=str(settings.BASE_DIR / 'backups'))
        parser.add_argument('--days', type=int, default=7)

    def handle(self, *args, **options):
        target = __import__('pathlib').Path(options['dir'])
        target.mkdir(parents=True, exist_ok=True)
        now = timezone.now()
        name = target / f'kb-backup-{now:%Y%m%d-%H%M%S}.zip'
        dump = StringIO()
        call_command('dumpdata', exclude=['contenttypes', 'auth.permission', 'sessions', 'admin.logentry'],
                     indent=1, stdout=dump)
        with zipfile.ZipFile(name, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('data.json', dump.getvalue())
            media = settings.MEDIA_ROOT
            if media.exists():
                for path in media.rglob('*'):
                    if path.is_file():
                        archive.write(path, 'media/' + path.relative_to(media).as_posix())
        border = now - timedelta(days=options['days'])
        removed = 0
        for old in target.glob('kb-backup-*.zip'):
            if old != name and timezone.datetime.fromtimestamp(old.stat().st_mtime, timezone.utc) < border:
                old.unlink()
                removed += 1
        self.stdout.write(self.style.SUCCESS(f'Копия: {name}; удалено старых: {removed}'))
