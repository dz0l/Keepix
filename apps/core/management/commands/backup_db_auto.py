import glob
import gzip
import os
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = (
        'Автобекап только БД в BACKUP_DB_ROOT, хранить последние BACKUP_DB_KEEP_LAST файлов. '
        'Полный архив с медиа — отдельная команда (будет добавлена).'
    )

    def handle(self, *args, **options):
        backup_root = Path(settings.BACKUP_DB_ROOT)
        backup_root.mkdir(parents=True, exist_ok=True)

        db = settings.DATABASES['default']
        stamp = timezone.now().strftime('%Y%m%d_%H%M')
        out_path = backup_root / f'db_{stamp}.sql.gz'

        env = os.environ.copy()
        pwd = db.get('PASSWORD') or ''
        if pwd:
            env['PGPASSWORD'] = str(pwd)

        cmd = [
            'pg_dump',
            '-h',
            db.get('HOST', 'localhost'),
            '-p',
            str(db.get('PORT', '5432')),
            '-U',
            str(db.get('USER', '')),
            '-F',
            'p',
            str(db.get('NAME', '')),
        ]

        self.stdout.write('Running pg_dump (gzip) ...')
        with gzip.open(out_path, 'wb', compresslevel=9) as gz:
            subprocess.run(cmd, stdout=gz, check=True, env=env)

        self.stdout.write(self.style.SUCCESS(f'Saved {out_path}'))

        keep = max(1, int(settings.BACKUP_DB_KEEP_LAST))
        pattern = str(backup_root / 'db_*.sql.gz')
        files = sorted(glob.glob(pattern), key=lambda p: Path(p).stat().st_mtime, reverse=True)
        for old in files[keep:]:
            Path(old).unlink(missing_ok=True)
            self.stdout.write(f'Removed old backup {old}')
