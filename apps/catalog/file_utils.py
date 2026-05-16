from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings

from keepix.public_url import build_object_public_url
from PIL import Image, UnidentifiedImageError
import qrcode

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

from .models import CatalogObject, PhotoAttachment

PHOTO_INPUT_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif', '.tiff', '.tif'}
STORE_FORMAT = 'JPEG'
STORE_EXT = '.jpg'
_FILE_SLOT_RE = re.compile(r'_(\d{2})$')


def _media_root(code: str) -> Path:
    return Path(settings.MEDIA_ROOT) / 'objects' / code


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _save_stream(uploaded_file, destination: Path) -> None:
    with destination.open('wb') as out:
        for chunk in uploaded_file.chunks():
            out.write(chunk)


def parse_object_code(raw: str) -> str | None:
    """ID из URL объекта (/objects/0001/) или из строки только с цифрами ID."""
    raw = (raw or '').strip()
    if not raw:
        return None

    url_match = re.search(r'/objects/(\d{1,4})(?:/|[\s?#]|$)', raw, re.I)
    if url_match:
        num = int(url_match.group(1))
        if 1 <= num <= 9999:
            return f'{num:04d}'

    compact = re.sub(r'\s+', '', raw)
    if re.fullmatch(r'\d{1,4}', compact):
        num = int(compact)
        if 1 <= num <= 9999:
            return f'{num:04d}'

    return None


def _slot_from_stem(code: str, stem: str) -> int | None:
    if not stem.startswith(f'{code}_'):
        return None
    match = _FILE_SLOT_RE.search(stem)
    if not match:
        return None
    return int(match.group(1))


def _max_existing_file_slot(code: str, subdir: str, extension: str) -> int:
    max_slot = 0
    base = _media_root(code) / subdir
    if base.is_dir():
        for path in base.glob(f'{code}_*{extension}'):
            stem = path.stem
            if stem.startswith('preview_'):
                stem = stem.removeprefix('preview_')
            slot = _slot_from_stem(code, stem)
            if slot is not None:
                max_slot = max(max_slot, slot)
    return max_slot


def next_photo_slot(obj) -> int:
    """Следующий свободный номер файла (не sort_order — он может быть 0 после удаления фото)."""
    code = obj.code
    max_slot = _max_existing_file_slot(code, 'photos', STORE_EXT)
    for path in obj.photos.values_list('path_original', flat=True):
        stem = Path(path).stem
        slot = _slot_from_stem(code, stem)
        if slot is not None:
            max_slot = max(max_slot, slot)
    return max_slot + 1


def next_pdf_slot(obj) -> int:
    code = obj.code
    max_slot = _max_existing_file_slot(code, 'pdf', '.pdf')
    for path in obj.pdfs.values_list('path', flat=True):
        stem = Path(path).stem
        slot = _slot_from_stem(code, stem)
        if slot is not None:
            max_slot = max(max_slot, slot)
    return max_slot + 1


def next_photo_sort_order(obj) -> int:
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


def save_qr_png(obj: CatalogObject) -> str:
    code = obj.code
    base_dir = _media_root(code) / 'qr'
    _ensure_dir(base_dir)
    file_path = base_dir / f'{code}.png'

    url = build_object_public_url(obj.code)
    qr = qrcode.QRCode(version=None, box_size=8, border=2)
    qr.add_data(url)
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
