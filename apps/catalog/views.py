import logging
import re
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from .file_utils import (
    delete_paths,
    delete_photo_files,
    next_pdf_slot,
    next_photo_slot,
    next_photo_sort_order,
    parse_object_code,
    save_pdf,
    save_photo,
    save_qr_png,
)
from .forms import CatalogObjectForm
from .models import CatalogObject, ObjectIdSequence, PdfAttachment, PhotoAttachment
from .permissions import catalog_admin_required
from .printing import (
    build_compact_sheets,
    build_print_pages,
    fetch_objects_for_print,
    render_cards_pdf,
    render_compact_pdf,
)
from .services import (
    delete_pdf,
    delete_photo,
    ensure_object_media_dirs,
    record_placement_change,
    reorder_photos,
    set_primary_photo,
    soft_delete_object,
)

logger = logging.getLogger('keepix.catalog')

PER_PAGE_DEFAULT = 20
PER_PAGE_OPTIONS = (20, 40, 60)


def _parse_per_page(raw: str) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return PER_PAGE_DEFAULT
    return value if value in PER_PAGE_OPTIONS else PER_PAGE_DEFAULT

SORT_FIELDS = {
    'code': 'code',
    'sender': 'sender',
    'obj_type': 'obj_type',
    'description': 'description',
    'placement': 'placement',
}


def _active_queryset():
    return CatalogObject.objects.filter(status=CatalogObject.Status.ACTIVE)


def _normal_condition_only(qs):
    return qs.filter(condition=CatalogObject.Condition.ACTIVE)


def _show_hidden_requested(request) -> bool:
    return (
        request.user.is_authenticated
        and request.user.is_catalog_admin()
        and request.GET.get('show_hidden') == '1'
    )


def _list_queryset(request):
    qs = _active_queryset()
    if not _show_hidden_requested(request):
        qs = _normal_condition_only(qs)
    return qs


def _object_access_queryset(user):
    qs = _active_queryset()
    if not user.is_catalog_admin():
        qs = _normal_condition_only(qs)
    return qs


def _apply_search(qs, query: str):
    query = query.strip()
    if not query:
        return qs

    text_filter = (
        Q(sender__icontains=query)
        | Q(description__icontains=query)
        | Q(comment__icontains=query)
        | Q(placement__icontains=query)
        | Q(tags__icontains=query)
        | Q(obj_type__icontains=query)
    )

    code_filter = Q()
    if query.isdigit():
        num = int(query)
        if 1 <= num <= 9999:
            code_filter = Q(code=f'{num:04d}')
    elif re.fullmatch(r'\d{4}', query):
        code_filter = Q(code=query)

    return qs.filter(text_filter | code_filter).distinct()


def _apply_sort(qs, sort: str, order: str):
    if sort not in SORT_FIELDS:
        return qs.order_by('-updated_at', 'code')
    field = SORT_FIELDS[sort]
    descending = order == 'desc'
    primary = f'-{field}' if descending else field
    return qs.order_by(primary, 'code')


def _build_sort_urls(request, sort: str, order: str) -> dict[str, str]:
    base = request.GET.copy()
    base.pop('page', None)
    urls: dict[str, str] = {}
    for field in SORT_FIELDS:
        params = base.copy()
        params['sort'] = field
        if sort == field and order == 'asc':
            params['order'] = 'desc'
        else:
            params['order'] = 'asc'
        urls[field] = params.urlencode()
    return urls


def _build_per_page_urls(request) -> dict[int, str]:
    base = request.GET.copy()
    base.pop('page', None)
    urls: dict[int, str] = {}
    for value in PER_PAGE_OPTIONS:
        params = base.copy()
        params['per_page'] = str(value)
        urls[value] = params.urlencode()
    return urls


def _check_version(obj: CatalogObject, posted: str) -> bool:
    if not posted:
        return True
    parsed = parse_datetime(posted)
    if parsed is None:
        return True
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return obj.updated_at == parsed


def _attach_uploaded_files(obj: CatalogObject, form: CatalogObjectForm) -> list[str]:
    saved_paths: list[str] = []
    for photo_file in form.cleaned_data.get('photos') or []:
        file_slot = next_photo_slot(obj)
        rel, rel_preview, size = save_photo(obj.code, photo_file, file_slot)
        saved_paths.extend([rel, rel_preview])
        is_first = not obj.photos.exists()
        PhotoAttachment.objects.create(
            catalog_object=obj,
            path_original=rel,
            path_preview=rel_preview,
            original_name=photo_file.name,
            sort_order=next_photo_sort_order(obj),
            is_primary=is_first,
            size=size,
        )

    for pdf_file in form.cleaned_data.get('pdfs') or []:
        file_slot = next_pdf_slot(obj)
        rel, size = save_pdf(obj.code, pdf_file, file_slot)
        saved_paths.append(rel)
        PdfAttachment.objects.create(
            catalog_object=obj,
            path=rel,
            original_name=pdf_file.name,
            size=size,
        )
    return saved_paths


def _form_context(form, mode, obj=None):
    photos = []
    pdfs = []
    if obj:
        photos = list(obj.photos.order_by('sort_order', 'pk'))
        pdfs = list(obj.pdfs.order_by('pk'))
    return {
        'form': form,
        'mode': mode,
        'obj': obj,
        'photos': photos,
        'pdfs': pdfs,
        'photo_order': ','.join(str(p.pk) for p in photos),
    }


@login_required
def object_list(request):
    show_hidden = _show_hidden_requested(request)
    qs = (
        _list_queryset(request)
        .prefetch_related(
            Prefetch(
                'photos',
                queryset=PhotoAttachment.objects.order_by('sort_order', 'pk'),
            )
        )
    )

    q = request.GET.get('q', '')
    qs = _apply_search(qs, q)

    obj_type = request.GET.get('type', '')
    if obj_type and obj_type in dict(CatalogObject.ObjectType.choices):
        qs = qs.filter(obj_type=obj_type)

    sort = request.GET.get('sort', '')
    order = request.GET.get('order', 'asc')
    if order not in {'asc', 'desc'}:
        order = 'asc'
    qs = _apply_sort(qs, sort, order)

    per_page = _parse_per_page(request.GET.get('per_page', ''))
    paginator = Paginator(qs, per_page)
    page = paginator.get_page(request.GET.get('page'))

    query_params = request.GET.copy()
    query_params.pop('page', None)
    per_page_urls = _build_per_page_urls(request)

    return render(
        request,
        'catalog/object_list.html',
        {
            'page': page,
            'q': q,
            'obj_type': obj_type,
            'sort': sort,
            'order': order,
            'per_page': per_page,
            'per_page_links': [
                {'value': n, 'query': per_page_urls[n], 'active': n == per_page}
                for n in PER_PAGE_OPTIONS
            ],
            'sort_urls': _build_sort_urls(request, sort, order),
            'type_choices': CatalogObject.ObjectType.choices,
            'query_string': query_params.urlencode(),
            'show_hidden': show_hidden,
            'is_admin': request.user.is_catalog_admin(),
        },
    )


@login_required
def object_detail(request, code: str):
    obj = get_object_or_404(
        _object_access_queryset(request.user).prefetch_related('photos', 'pdfs'),
        code=code,
    )
    placement_history = obj.placement_history.select_related('changed_by')[:20]
    return render(
        request,
        'catalog/object_detail.html',
        {
            'obj': obj,
            'photos': obj.photos.order_by('sort_order', 'pk'),
            'pdfs': obj.pdfs.all(),
            'placement_history': placement_history,
            'is_admin': request.user.is_catalog_admin(),
        },
    )


@catalog_admin_required
@transaction.atomic
def object_create(request):
    if request.method == 'POST':
        form = CatalogObjectForm(request.POST, request.FILES)
        if form.is_valid():
            saved_paths: list[str] = []
            try:
                code = ObjectIdSequence.allocate_code()
                obj = form.save(commit=False)
                obj.code = code
                obj.created_by = request.user
                obj.updated_by = request.user
                obj.save()

                ensure_object_media_dirs(code)
                saved_paths.append(save_qr_png(obj))

                if obj.placement.strip():
                    record_placement_change(obj, request.user, '', obj.placement)

                saved_paths.extend(_attach_uploaded_files(obj, form))
            except (ValidationError, ValueError) as exc:
                delete_paths(saved_paths)
                messages.error(request, str(exc) if isinstance(exc, ValueError) else '; '.join(exc.messages))
                return render(request, 'catalog/object_form.html', _form_context(form, 'create'))
            except Exception:
                logger.exception('object create failed during file save')
                delete_paths(saved_paths)
                messages.error(request, 'Ошибка при сохранении файлов.')
                return render(request, 'catalog/object_form.html', _form_context(form, 'create'))

            logger.info('object %s created by %s', code, request.user.username)
            messages.success(request, f'Объект {code} добавлен.')
            return redirect('catalog:object_detail', code=code)
    else:
        form = CatalogObjectForm()

    return render(request, 'catalog/object_form.html', _form_context(form, 'create'))


@catalog_admin_required
@transaction.atomic
def object_edit(request, code: str):
    obj = get_object_or_404(_active_queryset().select_for_update(), code=code)
    old_placement = obj.placement

    if request.method == 'POST':
        if not _check_version(obj, request.POST.get('updated_at', '')):
            messages.error(
                request,
                'Запись была изменена другим пользователем. Обновите страницу и повторите.',
            )
            form = CatalogObjectForm(
                request.POST,
                request.FILES,
                instance=obj,
                existing_photo_count=obj.photos.count(),
                existing_pdf_count=obj.pdfs.count(),
            )
            return render(request, 'catalog/object_form.html', _form_context(form, 'edit', obj))

        form = CatalogObjectForm(
            request.POST,
            request.FILES,
            instance=obj,
            existing_photo_count=obj.photos.count(),
            existing_pdf_count=obj.pdfs.count(),
        )
        if form.is_valid():
            saved_paths: list[str] = []
            try:
                order_raw = request.POST.get('photo_order', '').strip()
                if order_raw:
                    ordered_ids = [int(x) for x in order_raw.split(',') if x.strip().isdigit()]
                    if ordered_ids:
                        reorder_photos(obj, ordered_ids)

                obj = form.save(commit=False)
                obj.updated_by = request.user
                obj.save()
                record_placement_change(obj, request.user, old_placement, obj.placement)
                saved_paths.append(save_qr_png(obj))
                saved_paths.extend(_attach_uploaded_files(obj, form))
            except ValueError as exc:
                delete_paths(saved_paths)
                messages.error(request, str(exc))
                return render(request, 'catalog/object_form.html', _form_context(form, 'edit', obj))
            except Exception:
                logger.exception('object edit failed during file save')
                delete_paths(saved_paths)
                messages.error(request, 'Ошибка при сохранении файлов.')
                return render(request, 'catalog/object_form.html', _form_context(form, 'edit', obj))

            logger.info('object %s updated by %s', obj.code, request.user.username)
            messages.success(request, f'Объект {obj.code} сохранён.')
            return redirect('catalog:object_detail', code=obj.code)
    else:
        form = CatalogObjectForm(
            instance=obj,
            existing_photo_count=obj.photos.count(),
            existing_pdf_count=obj.pdfs.count(),
        )

    return render(request, 'catalog/object_form.html', _form_context(form, 'edit', obj))


@catalog_admin_required
def object_delete(request, code: str):
    obj = get_object_or_404(_active_queryset(), code=code)

    if request.method == 'POST':
        if request.POST.get('confirm') != 'yes':
            messages.error(request, 'Подтвердите удаление.')
            return render(request, 'catalog/object_confirm_delete.html', {'obj': obj})

        soft_delete_object(obj, request.user)
        messages.success(request, f'Объект {code} удалён.')
        return redirect('catalog:object_list')

    return render(request, 'catalog/object_confirm_delete.html', {'obj': obj})


@catalog_admin_required
@require_POST
def photo_delete(request, code: str, photo_id: int):
    obj = get_object_or_404(_active_queryset(), code=code)
    try:
        delete_photo(obj, photo_id)
        messages.success(request, 'Фото удалено.')
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect('catalog:object_edit', code=code)


@catalog_admin_required
@require_POST
def photo_set_primary(request, code: str, photo_id: int):
    obj = get_object_or_404(_active_queryset(), code=code)
    try:
        set_primary_photo(obj, photo_id)
        messages.success(request, 'Главное фото обновлено.')
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect('catalog:object_edit', code=code)


@catalog_admin_required
@require_POST
def pdf_delete(request, code: str, pdf_id: int):
    obj = get_object_or_404(_active_queryset(), code=code)
    try:
        delete_pdf(obj, pdf_id)
        messages.success(request, 'PDF удалён.')
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect('catalog:object_edit', code=code)


@login_required
def object_qr(request, code: str):
    obj = get_object_or_404(_active_queryset(), code=code)
    rel = save_qr_png(obj)
    full = Path(settings.MEDIA_ROOT) / rel
    if not full.is_file():
        raise Http404()
    return HttpResponse(full.read_bytes(), content_type='image/png')


@login_required
def qr_search(request):
    if request.method == 'GET':
        return redirect(f'{reverse("catalog:object_list")}?qr=1')

    if request.method == 'POST':
        code = parse_object_code(request.POST.get('code', ''))
        if not code:
            messages.error(request, 'Введите корректный ID объекта (до 4 цифр).')
            return render(request, 'catalog/qr_search.html')
        if not _object_access_queryset(request.user).filter(code=code).exists():
            messages.error(request, f'Объект {code} не найден.')
            return render(request, 'catalog/qr_search.html')
        return redirect('catalog:object_detail', code=code)
    return render(request, 'catalog/qr_search.html')


def _parse_print_codes(raw) -> list[str]:
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.split(',') if p.strip()]
    else:
        parts = [str(item).strip() for item in raw if str(item).strip()]

    codes: list[str] = []
    for part in parts:
        code = part if re.fullmatch(r'\d{4}', part) else parse_object_code(part)
        if code and code not in codes:
            codes.append(code)
    return codes


def _pdf_response(pdf_bytes: bytes, filename: str, *, inline: bool) -> HttpResponse:
    disposition = 'inline' if inline else 'attachment'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    return response


@login_required
def object_print_pdf(request, code: str):
    obj = get_object_or_404(_active_queryset().prefetch_related('photos'), code=code)
    try:
        pdf_bytes = render_cards_pdf(build_print_pages([obj]))
    except Exception:
        logger.exception('print pdf failed for %s', code)
        raise Http404() from None
    return _pdf_response(pdf_bytes, f'keepix_{code}.pdf', inline=False)


@login_required
def bulk_print_submit(request):
    if request.method != 'POST':
        return redirect('catalog:object_list')
    codes = _parse_print_codes(request.POST.getlist('codes'))
    if not codes:
        messages.error(request, 'Выберите хотя бы один объект для печати.')
        return redirect('catalog:object_list')
    return redirect(f'{reverse("catalog:print_bulk_pdf")}?codes={",".join(codes)}')


@login_required
def print_bulk_pdf(request):
    codes = _parse_print_codes(request.GET.get('codes', ''))
    objects = list(fetch_objects_for_print(codes))
    if not objects:
        messages.error(request, 'Объекты для печати не найдены.')
        return redirect('catalog:object_list')
    try:
        pdf_bytes = render_compact_pdf(build_compact_sheets(objects))
    except Exception:
        logger.exception('bulk print pdf failed')
        raise Http404() from None
    if len(objects) == 1:
        filename = f'keepix_{objects[0].code}_list.pdf'
    else:
        filename = f'keepix_list_{len(objects)}.pdf'
    return _pdf_response(pdf_bytes, filename, inline=False)
