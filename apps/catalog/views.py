import logging
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .forms import CatalogObjectForm
from .models import CatalogObject, ObjectIdSequence
from .permissions import catalog_admin_required
from .services import (
    ensure_object_media_dirs,
    record_placement_change,
    soft_delete_object,
)

logger = logging.getLogger('keepix.catalog')

PER_PAGE = 20


def _active_queryset():
    return CatalogObject.objects.filter(status=CatalogObject.Status.ACTIVE)


def _apply_search(qs, query: str):
    query = query.strip()
    if not query:
        return qs

    text_filter = (
        Q(sender__icontains=query)
        | Q(description__icontains=query)
        | Q(comment__icontains=query)
        | Q(placement__icontains=query)
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


def _check_version(obj: CatalogObject, posted: str) -> bool:
    if not posted:
        return True
    parsed = parse_datetime(posted)
    if parsed is None:
        return True
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return obj.updated_at == parsed


@login_required
def object_list(request):
    qs = _active_queryset().order_by('-updated_at', 'code')

    q = request.GET.get('q', '')
    qs = _apply_search(qs, q)

    obj_type = request.GET.get('type', '')
    if obj_type and obj_type in dict(CatalogObject.ObjectType.choices):
        qs = qs.filter(obj_type=obj_type)

    condition = request.GET.get('condition', '')
    if condition and condition in dict(CatalogObject.Condition.choices):
        qs = qs.filter(condition=condition)

    paginator = Paginator(qs, PER_PAGE)
    page = paginator.get_page(request.GET.get('page'))

    query_params = request.GET.copy()
    query_params.pop('page', None)

    return render(
        request,
        'catalog/object_list.html',
        {
            'page': page,
            'q': q,
            'obj_type': obj_type,
            'condition': condition,
            'type_choices': CatalogObject.ObjectType.choices,
            'condition_choices': CatalogObject.Condition.choices,
            'query_string': query_params.urlencode(),
            'is_admin': request.user.is_catalog_admin(),
        },
    )


@login_required
def object_detail(request, code: str):
    obj = get_object_or_404(_active_queryset(), code=code)
    placement_history = obj.placement_history.select_related('changed_by')[:20]
    return render(
        request,
        'catalog/object_detail.html',
        {
            'obj': obj,
            'placement_history': placement_history,
            'is_admin': request.user.is_catalog_admin(),
        },
    )


@catalog_admin_required
@transaction.atomic
def object_create(request):
    if request.method == 'POST':
        form = CatalogObjectForm(request.POST)
        if form.is_valid():
            try:
                code = ObjectIdSequence.allocate_code()
            except ValidationError as exc:
                messages.error(request, '; '.join(getattr(exc, 'messages', [str(exc)])))
                return render(request, 'catalog/object_form.html', {'form': form, 'mode': 'create'})

            obj = form.save(commit=False)
            obj.code = code
            obj.created_by = request.user
            obj.updated_by = request.user
            obj.save()

            ensure_object_media_dirs(code)
            if obj.placement.strip():
                record_placement_change(obj, request.user, '', obj.placement)

            logger.info('object %s created by %s', code, request.user.username)
            messages.success(request, f'Объект {code} добавлен.')
            return redirect('catalog:object_detail', code=code)
    else:
        form = CatalogObjectForm()

    return render(request, 'catalog/object_form.html', {'form': form, 'mode': 'create'})


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
            form = CatalogObjectForm(request.POST, instance=obj)
            return render(
                request,
                'catalog/object_form.html',
                {'form': form, 'mode': 'edit', 'obj': obj},
            )

        form = CatalogObjectForm(request.POST, instance=obj)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            record_placement_change(obj, request.user, old_placement, obj.placement)
            logger.info('object %s updated by %s', obj.code, request.user.username)
            messages.success(request, f'Объект {obj.code} сохранён.')
            return redirect('catalog:object_detail', code=obj.code)
    else:
        form = CatalogObjectForm(instance=obj)

    return render(
        request,
        'catalog/object_form.html',
        {'form': form, 'mode': 'edit', 'obj': obj},
    )


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
