import gzip
import io
import os
import subprocess
import tarfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Полный архив .tar.gz: дамп PostgreSQL (gzip) + каталог media/.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            help='Путь к выходному .tar.gz (по умолчанию BACKUP_FULL_ROOT/keepix_full_<timestamp>.tar.gz)',
        )

    def handle(self, *args, **options):
        backup_root = Path(settings.BACKUP_FULL_ROOT)
        backup_root.mkdir(parents=True, exist_ok=True)

        stamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        out_path = Path(options['output']) if options.get('output') else backup_root / f'keepix_full_{stamp}.tar.gz'
        out_path = out_path.resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if out_path.exists():
            raise CommandError(f'Файл уже существует: {out_path}')

        db = settings.DATABASES['default']
        env = os.environ.copy()
        pwd = db.get('PASSWORD') or ''
        if pwd:
            env['PGPASSWORD'] = str(pwd)

        dump_name = 'database.sql.gz'
        dump_tmp = out_path.parent / f'.{out_path.stem}_{stamp}_db.sql.gz'

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
        try:
            with gzip.open(dump_tmp, 'wb', compresslevel=9) as gz:
                subprocess.run(cmd, stdout=gz, check=True, env=env)
        except subprocess.CalledProcessError as exc:
            dump_tmp.unlink(missing_ok=True)
            raise CommandError(f'pg_dump failed: {exc}') from exc

        media_root = Path(settings.MEDIA_ROOT)
        manifest = (
            f'Keepix full backup\n'
            f'created_at={timezone.now().isoformat()}\n'
            f'database={db.get("NAME")}\n'
            f'media_root={media_root}\n'
        )

        self.stdout.write(f'Creating archive {out_path} ...')
        try:
            with tarfile.open(out_path, 'w:gz') as tar:
                tar.add(dump_tmp, arcname=dump_name)
                if media_root.is_dir():
                    tar.add(media_root, arcname='media')
                info = tarfile.TarInfo(name='MANIFEST.txt')
                data = manifest.encode('utf-8')
                info.size = len(data)
                tar.addfile(info, fileobj=io.BytesIO(data))
        finally:
            dump_tmp.unlink(missing_ok=True)

        size_mb = out_path.stat().st_size / (1024 * 1024)
        self.stdout.write(self.style.SUCCESS(f'Saved {out_path} ({size_mb:.1f} MiB)'))
