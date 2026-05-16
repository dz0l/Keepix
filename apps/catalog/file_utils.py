from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from PIL import Image, UnidentifiedImageError
import qrcode

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

from .models import PhotoAttachment

PHOTO_INPUT_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif', '.tiff', '.tif'}
STORE_FORMAT = 'JPEG'
STORE_EXT = '.jpg'


def _media_root(code: str) -> Path:
    return Path(settings.MEDIA_ROOT) / 'objects' / code


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _save_stream(uploaded_file, destination: Path) -> None:
    with destination.open('wb') as out:
        for chunk in uploaded_file.chunks():
            out.write(chunk)


def parse_object_code(raw: str) -> str | None:
    raw = (raw or '').strip()
    if not raw:
        return None
    match = re.search(r'\d{1,4}', raw)
    if not match:
        return None
    num = int(match.group())
    if num < 1 or num > 9999:
        return None
    return f'{num:04d}'


def next_photo_slot(obj) -> int:
    last = obj.photos.order_by('-sort_order').values_list('sort_order', flat=True).first()
    return (last or 0) + 1


def save_photo(code: str, uploaded_file, slot: int) -> tuple[str, str, int]:
    ext = Path(uploaded_file.name).suffix.lower()
    if ext not in PHOTO_INPUT_EXTENSIONS:
        raise ValueError('Неподдерживаемый формат изображения.')

    max_size = settings.MAX_PHOTO_SIZE_MB * 1024 * 1024
    if uploaded_file.size > max_size:
        raise ValueError(f'Размер фото превышает {settings.MAX_PHOTO_SIZE_MB} МБ.')

    base_dir = _media_root(code) / 'photos'
    _ensure_dir(base_dir)

    uploaded_file.seek(0)
    try:
        with Image.open(uploaded_file) as probe:
            probe.verify()
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError('Неподдерживаемый или повреждённый файл изображения.') from exc

    if image.mode in ('RGBA', 'LA', 'P'):
        image = image.convert('RGB')
    elif image.mode != 'RGB':
        image = image.convert('RGB')

    filename = f'{code}_{slot:02d}{STORE_EXT}'
    file_path = base_dir / filename
    preview_path = base_dir / f'preview_{filename}'

    image.save(file_path, format=STORE_FORMAT, optimize=True, quality=85)
    preview = image.copy()
    preview.thumbnail((settings.PHOTO_PREVIEW_MAX_PX, settings.PHOTO_PREVIEW_MAX_PX))
    preview.save(preview_path, format=STORE_FORMAT, optimize=True, quality=85)

    rel = file_path.relative_to(settings.MEDIA_ROOT).as_posix()
    rel_preview = preview_path.relative_to(settings.MEDIA_ROOT).as_posix()
    return rel, rel_preview, file_path.stat().st_size


def save_pdf(code: str, uploaded_file, slot: int) -> tuple[str, int]:
    ext = Path(uploaded_file.name).suffix.lower()
    if ext != '.pdf':
        raise ValueError('Допускаются только PDF-файлы.')

    max_size = settings.MAX_PDF_SIZE_MB * 1024 * 1024
    if uploaded_file.size > max_size:
        raise ValueError(f'Размер PDF превышает {settings.MAX_PDF_SIZE_MB} МБ.')

    uploaded_file.seek(0)
    if uploaded_file.read(5) != b'%PDF-':
        raise ValueError('Файл не является корректным PDF.')
    uploaded_file.seek(0)

    base_dir = _media_root(code) / 'pdf'
    _ensure_dir(base_dir)

    filename = f'{code}_{slot:02d}.pdf'
    file_path = base_dir / filename
    _save_stream(uploaded_file, file_path)

    rel = file_path.relative_to(settings.MEDIA_ROOT).as_posix()
    return rel, file_path.stat().st_size


def save_qr_png(code: str) -> str:
    base_dir = _media_root(code) / 'qr'
    _ensure_dir(base_dir)
    file_path = base_dir / f'{code}.png'

    qr = qrcode.QRCode(version=None, box_size=8, border=2)
    qr.add_data(code)
    qr.make(fit=True)
    image = qr.make_image(fill_color='black', back_color='white')
    image.save(file_path, format='PNG')

    return file_path.relative_to(settings.MEDIA_ROOT).as_posix()


def delete_paths(paths: list[str]) -> None:
    for rel in paths:
        full = Path(settings.MEDIA_ROOT) / rel
        if full.is_file():
            full.unlink()


def delete_photo_files(photo: PhotoAttachment) -> None:
    paths = [photo.path_original]
    if photo.path_preview:
        paths.append(photo.path_preview)
    delete_paths(paths)


def ensure_primary_photo(obj) -> None:
    photos = list(obj.photos.order_by('sort_order', 'pk'))
    if not photos:
        return
    if any(p.is_primary for p in photos):
        return
    photos[0].is_primary = True
    photos[0].save(update_fields=['is_primary'])
