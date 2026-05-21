from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.management.commands._staff_user_helpers import (
    confirm_destructive_action,
    ensure_not_last_active_admin,
    get_user,
)
from apps.accounts.models import User


class Command(BaseCommand):
    help = (
        'Удалить пользователя из базы. Связи «кем создан/изменён» у объектов обнулятся (SET_NULL). '
        'Чтобы только запретить вход, используйте deactivate_staff_user.'
    )

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Имя пользователя (username)')
        parser.add_argument(
            '--yes',
            '-y',
            action='store_true',
            help='Подтвердить удаление без запроса (для скриптов и non-TTY)',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        user = get_user(options['username'])
        role_label = User.Role(user.role).label

        ensure_not_last_active_admin(user)

        confirm_destructive_action(
            f'Удалить пользователя {user.username!r} ({role_label}) безвозвратно?',
            assume_yes=options['yes'],
        )

        username = user.username
        user.delete()

        self.stdout.write(self.style.SUCCESS(f'Пользователь {username} удалён.'))
