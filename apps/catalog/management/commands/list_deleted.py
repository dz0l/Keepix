from django.core.management.base import BaseCommand

from apps.catalog.models import CatalogObject


class Command(BaseCommand):
    help = 'Print deleted catalogue objects (status=deleted) to stdout; not surfaced in web UI.'

    def handle(self, *args, **options):
        qs = (
            CatalogObject.objects.filter(status=CatalogObject.Status.DELETED)
            .order_by('-deleted_at', 'code')
        )
        count = qs.count()
        self.stdout.write(f'Удалённых записей: {count}')
        for obj in qs:
            desc = ((obj.description or '')[:80]).replace('\n', ' ')
            self.stdout.write(
                f'{obj.code}\tdeleted_at={obj.deleted_at}\t'
                f'от={obj.sender}\tтип={obj.obj_type}\tописание={desc!r}'
            )
