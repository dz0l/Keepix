import sys

from django.core.management.base import CommandError

from apps.accounts.models import User


def resolve_username(username: str) -> str:
    value = (username or '').strip()
    if not value:
        raise CommandError('Укажите имя пользователя (username).')
    return value


def get_user(username: str) -> User:
    name = resolve_username(username)
    try:
        return User.objects.get(username=name)
    except User.DoesNotExist as exc:
        raise CommandError(f'Пользователь {name!r} не найден.') from exc


def active_admin_count(*, exclude_pk: int | None = None) -> int:
    qs = User.objects.filter(role=User.Role.ADMIN, is_active=True)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.count()


def ensure_not_last_active_admin(user: User) -> None:
    if user.role != User.Role.ADMIN or not user.is_active:
        return
    if active_admin_count(exclude_pk=user.pk) == 0:
        raise CommandError('Нельзя убрать последнего активного администратора.')


def confirm_destructive_action(message: str, *, assume_yes: bool) -> None:
    if assume_yes:
        return
    if sys.stdin.isatty():
        answer = input(f'{message} [y/N]: ').strip().lower()
        if answer not in {'y', 'yes', 'д', 'да'}:
            raise CommandError('Отменено.')
        return
    raise CommandError('Неинтерактивный режим: добавьте флаг --yes.')
