from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.management.commands._staff_user_helpers import (
    ensure_not_last_active_admin,
    get_user,
)
from apps.accounts.models import User


class Command(BaseCommand):
    help = (
        'Запретить вход пользователю (is_active=False). '
        'Учётная запись остаётся в базе.'
    )

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Имя пользователя (username)')

    @transaction.atomic
    def handle(self, *args, **options):
        user = get_user(options['username'])

        if not user.is_active:
            self.stdout.write(
                self.style.WARNING(f'Пользователь {user.username} уже отключён (is_active=False).')
            )
            return

        ensure_not_last_active_admin(user)

        user.is_active = False
        user.failed_login_attempts = 0
        user.locked_until = None
        user.save(update_fields=['is_active', 'failed_login_attempts', 'locked_until'])

        role_label = User.Role(user.role).label
        self.stdout.write(
            self.style.SUCCESS(
                f'Пользователь {user.username} ({role_label}) отключён — вход запрещён.'
            )
        )
