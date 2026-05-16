from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from weasyprint import CSS, HTML

from .models import CatalogObject


def _layout_class(photo_count: int) -> str:
    if photo_count <= 1:
        return 'photos-1'
    if photo_count <= 3:
        return 'photos-row'
    return 'photos-grid'


def _photo_file_uri(rel_path: str, media_root: Path) -> str | None:
    full = media_root / rel_path
    if full.is_file():
        return full.resolve().as_uri()
    return None


def build_print_pages(objects) -> list[dict]:
    media_root = Path(settings.MEDIA_ROOT)
    pages: list[dict] = []
    for obj in objects:
        photos = list(obj.photos.order_by('sort_order', 'pk'))
        photo_uris = [
            uri
            for photo in photos
            if (uri := _photo_file_uri(photo.path_original, media_root))
        ]
        pages.append(
            {
                'obj': obj,
                'photo_uris': photo_uris,
                'layout_class': _layout_class(len(photo_uris)),
            }
        )
    return pages


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
