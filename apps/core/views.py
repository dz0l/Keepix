from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect, render

from apps.accounts.models import User
from apps.catalog.models import CatalogObject, PdfAttachment


def health_live(request):
    return HttpResponse('ok', content_type='text/plain')


def health_ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        return HttpResponse('db-unavailable', status=503, content_type='text/plain')
    return HttpResponse('ok', content_type='text/plain')


@login_required
def home(request):
    return redirect('catalog:object_list')


def _authorize_media_rel_path(user, rel_normalized: str) -> bool:
    parts = rel_normalized.strip('/').split('/')
    if len(parts) < 3 or parts[0] != 'objects':
        return False
    code = parts[1]
    if len(code) != 4:
        return False
    prefix = '/'.join(parts[:3])
    if prefix not in {f'objects/{code}/photos', f'objects/{code}/pdf', f'objects/{code}/qr'}:
        return False

    try:
        obj = CatalogObject.objects.get(pk=code)
    except CatalogObject.DoesNotExist:
        return False

    if obj.status == CatalogObject.Status.DELETED:
        return False

    if user.is_catalog_admin():
        return True
    return user.role == User.Role.USER


@login_required
def accel_media(request, rel_path: str):
    rel = rel_path.lstrip('/')
    if '..' in rel or rel.startswith('/'):
        raise Http404()

    full = Path(settings.MEDIA_ROOT) / rel
    try:
        full.resolve().relative_to(Path(settings.MEDIA_ROOT).resolve())
    except ValueError:
        raise Http404()

    if not _authorize_media_rel_path(request.user, rel):
        raise Http404()

    if not full.is_file():
        raise Http404()

    if not getattr(settings, 'USE_X_ACCEL', True):
        return FileResponse(full.open('rb'), filename=full.name)

    response = HttpResponse()
    internal = settings.INTERNAL_MEDIA_LOCATION.rstrip('/') + '/' + rel
    response['X-Accel-Redirect'] = internal
    response['Content-Type'] = ''
    return response


@login_required
def download_pdf_attachment(request, pk: int):
    try:
        att = PdfAttachment.objects.select_related('catalog_object').get(pk=pk)
    except PdfAttachment.DoesNotExist:
        raise Http404()

    obj = att.catalog_object
    if obj.status == CatalogObject.Status.DELETED:
        raise Http404()

    rel = att.path
    full = Path(settings.MEDIA_ROOT) / rel
    if not full.is_file():
        raise Http404()

    return FileResponse(full.open('rb'), as_attachment=True, filename=att.original_name)
