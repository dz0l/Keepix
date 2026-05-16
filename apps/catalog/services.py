import logging
import shutil
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .models import CatalogObject, PlacementHistory

logger = logging.getLogger('keepix.catalog')


def object_media_root(code: str) -> Path:
    return Path(settings.MEDIA_ROOT) / 'objects' / code


def ensure_object_media_dirs(code: str) -> None:
    base = object_media_root(code)
    for sub in ('photos', 'pdf', 'qr'):
        (base / sub).mkdir(parents=True, exist_ok=True)


def delete_object_media(code: str) -> None:
    root = object_media_root(code)
    if root.exists():
        shutil.rmtree(root)


def record_placement_change(obj: CatalogObject, user, old_placement: str, new_placement: str) -> None:
    if (old_placement or '').strip() == (new_placement or '').strip():
        return
    PlacementHistory.objects.create(
        catalog_object=obj,
        placement_text=new_placement or '',
        changed_by=user,
    )


def soft_delete_object(obj: CatalogObject, user) -> None:
    delete_object_media(obj.code)
    obj.photos.all().delete()
    obj.pdfs.all().delete()
    obj.status = CatalogObject.Status.DELETED
    obj.deleted_at = timezone.now()
    obj.deleted_by = user
    obj.save(update_fields=['status', 'deleted_at', 'deleted_by'])
    logger.info('object %s deleted by %s', obj.code, user.username)
