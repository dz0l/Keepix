"""Публичный базовый URL приложения (для QR и ссылок). Не через django.conf.settings — там доступны только UPPER_CASE."""

from django.conf import settings


def build_object_public_url(code: str) -> str:
    base = getattr(settings, 'KEEPIX_PUBLIC_BASE_URL', '') or _default_public_base_url()
    return f'{base.rstrip("/")}/objects/{code}/'


def _default_public_base_url() -> str:
    scheme = 'https' if settings.FORCE_HTTPS else 'http'
    port = getattr(settings, 'APP_PORT', '80')
    for host in settings.ALLOWED_HOSTS:
        host = host.strip()
        if not host or host in {'*', 'localhost', '127.0.0.1'}:
            continue
        if host.startswith('.'):
            continue
        base = f'{scheme}://{host}'
        if port and port not in {'80', '443'} and ':' not in host:
            base = f'{base}:{port}'
        return base
    if port and port not in {'80', '443'}:
        return f'{scheme}://127.0.0.1:{port}'
    return f'{scheme}://127.0.0.1'
