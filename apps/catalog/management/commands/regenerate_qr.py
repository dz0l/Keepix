from django.core.management.base import BaseCommand

from apps.catalog.file_utils import save_qr_png
from apps.catalog.models import CatalogObject


class Command(BaseCommand):
    help = (
        'Пересоздать PNG QR для активных объектов '
        '(после смены KEEPIX_PUBLIC_BASE_URL в .env; контейнер app перезапустить).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--code',
            help='Только один объект, например 0042',
        )

    def handle(self, *args, **options):
        qs = CatalogObject.objects.filter(status=CatalogObject.Status.ACTIVE)
        code = (options.get('code') or '').strip()
        if code:
            if len(code) <= 4 and code.isdigit():
                code = f'{int(code):04d}'
            qs = qs.filter(code=code)
            if not qs.exists():
                self.stderr.write(self.style.ERROR(f'Активный объект {code} не найден.'))
                return

        count = 0
        for obj in qs.iterator():
            save_qr_png(obj)
            count += 1

        self.stdout.write(self.style.SUCCESS(f'QR обновлены: {count}'))
