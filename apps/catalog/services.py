import logging
import shutil
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .file_utils import delete_photo_files, ensure_primary_photo
from .models import CatalogObject, PdfAttachment, PhotoAttachment, PlacementHistory

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


@transaction.atomic
def reorder_photos(obj: CatalogObject, ordered_ids: list[int]) -> None:
    photos = {p.pk: p for p in obj.photos.all()}
    if set(photos.keys()) != set(ordered_ids):
        raise ValueError('Некорректный список фото для сортировки.')
    for index, pk in enumerate(ordered_ids):
        photo = photos[pk]
        photo.sort_order = index
        photo.save(update_fields=['sort_order'])


@transaction.atomic
def set_primary_photo(obj: CatalogObject, photo_id: int) -> None:
    obj.photos.update(is_primary=False)
    photo = obj.photos.filter(pk=photo_id).first()
    if not photo:
        raise ValueError('Фото не найдено.')
    photo.is_primary = True
    photo.save(update_fields=['is_primary'])


@transaction.atomic
def delete_photo(obj: CatalogObject, photo_id: int) -> None:
    photo = obj.photos.filter(pk=photo_id).first()
    if not photo:
        raise ValueError('Фото не найдено.')
    was_primary = photo.is_primary
    delete_photo_files(photo)
    photo.delete()
    remaining = list(obj.photos.order_by('sort_order', 'pk'))
    for index, item in enumerate(remaining):
        if item.sort_order != index:
            item.sort_order = index
            item.save(update_fields=['sort_order'])
    if was_primary and remaining:
        remaining[0].is_primary = True
        remaining[0].save(update_fields=['is_primary'])
    ensure_primary_photo(obj)


@transaction.atomic
def delete_pdf(obj: CatalogObject, pdf_id: int) -> None:
    from .file_utils import delete_paths

    pdf = obj.pdfs.filter(pk=pdf_id).first()
    if not pdf:
        raise ValueError('PDF не найдено.')
    delete_paths([pdf.path])
    pdf.delete()
