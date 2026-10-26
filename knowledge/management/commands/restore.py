import tempfile
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Восстановление базы и файлов из резервной копии, созданной командой backup'

    def add_arguments(self, parser):
        parser.add_argument('archive')

    def handle(self, *args, **options):
        path = Path(options['archive'])
        if not path.is_file():
            raise CommandError(f'Файл не найден: {path}')
        with zipfile.ZipFile(path) as archive, tempfile.TemporaryDirectory() as tmp:
            if 'data.json' not in archive.namelist():
                raise CommandError('В архиве нет data.json')
            archive.extract('data.json', tmp)
            call_command('flush', interactive=False)
            call_command('loaddata', str(Path(tmp) / 'data.json'))
            for member in archive.namelist():
                if member.startswith('media/') and not member.endswith('/'):
                    destination = (settings.MEDIA_ROOT / member[len('media/'):]).resolve()
                    if settings.MEDIA_ROOT.resolve() not in destination.parents:
                        continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(archive.read(member))
        self.stdout.write(self.style.SUCCESS('Данные восстановлены'))
