from __future__ import annotations

import math
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from weasyprint import CSS, HTML

from .models import CatalogObject

COMPACT_OBJECTS_PER_SHEET = 3


def _photo_file_uri(rel_path: str, media_root: Path) -> str | None:
    full = media_root / rel_path
    if full.is_file():
        return full.resolve().as_uri()
    return None


def _photo_uris_for_object(obj, media_root: Path) -> list[str]:
    photos = list(obj.photos.order_by('sort_order', 'pk'))
    uris: list[str] = []
    for photo in photos:
        if uri := _photo_file_uri(photo.path_original, media_root):
            uris.append(uri)
    return uris


def build_print_pages(objects) -> list[dict]:
    """Карточка объекта: 1 объект = 1 страница, главное фото крупно."""
    media_root = Path(settings.MEDIA_ROOT)
    pages: list[dict] = []
    for obj in objects:
        uris = _photo_uris_for_object(obj, media_root)
        pages.append(
            {
                'obj': obj,
                'primary_photo_uri': uris[0] if uris else None,
                'extra_photo_uris': uris[1:],
            }
        )
    return pages


def build_compact_sheets(objects) -> list[dict]:
    """Сводка: до 3 объектов на альбомный A4."""
    media_root = Path(settings.MEDIA_ROOT)
    items: list[dict] = []
    for obj in objects:
        uris = _photo_uris_for_object(obj, media_root)
        items.append(
            {
                'obj': obj,
                'photo_uri': uris[0] if uris else None,
            }
        )

    sheets: list[dict] = []
    for index in range(0, len(items), COMPACT_OBJECTS_PER_SHEET):
        sheets.append({'items': items[index : index + COMPACT_OBJECTS_PER_SHEET]})
    return sheets


def fetch_objects_for_print(codes: list[str]):
    if not codes:
        return CatalogObject.objects.none()
    return (
        CatalogObject.objects.filter(
            status=CatalogObject.Status.ACTIVE,
            code__in=codes,
        )
        .prefetch_related('photos')
        .order_by('code')
    )


def render_cards_pdf(pages: list[dict]) -> bytes:
    html = render_to_string('catalog/print/document.html', {'pages': pages})
    css_path = Path(settings.BASE_DIR) / 'static' / 'css' / 'print_card.css'
    return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf(
        stylesheets=[CSS(filename=str(css_path))],
    )


def render_compact_pdf(sheets: list[dict]) -> bytes:
    html = render_to_string('catalog/print/compact_document.html', {'sheets': sheets})
    css_path = Path(settings.BASE_DIR) / 'static' / 'css' / 'print_compact.css'
    return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf(
        stylesheets=[CSS(filename=str(css_path))],
    )


def compact_sheet_count(object_count: int) -> int:
    if object_count <= 0:
        return 0
    return math.ceil(object_count / COMPACT_OBJECTS_PER_SHEET)
