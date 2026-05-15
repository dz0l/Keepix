import getpass
import os
import sys

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User


class Command(BaseCommand):
    help = (
        'Create a user (admin or user role). Password is never taken from CLI arguments '
        '(see README — Security). Use an interactive TTY with hidden prompts, or '
        'KEEPIX_NEW_USER_PASSWORD for non-interactive runs only.'
    )

    def add_arguments(self, parser):
        parser.add_argument('username', type=str)
        parser.add_argument(
            '--role',
            choices=['admin', 'user'],
            default='user',
            help='admin: full catalog access; user: view and print only',
        )
        parser.add_argument('--email', type=str, default='', help='Optional email')

    def _read_password(self) -> str:
        env_pw = os.environ.get('KEEPIX_NEW_USER_PASSWORD')
        if env_pw is not None:
            if env_pw == '':
                raise CommandError('KEEPIX_NEW_USER_PASSWORD is set but empty.')
            return env_pw

        if sys.stdin.isatty():
            p1 = getpass.getpass('Password (hidden): ')
            p2 = getpass.getpass('Password (again): ')
            if p1 != p2:
                raise CommandError('Passwords do not match.')
            if not p1:
                raise CommandError('Password must not be empty.')
            return p1

        raise CommandError(
            'Non-interactive session: export KEEPIX_NEW_USER_PASSWORD in the app '
            'container environment, or run with a TTY, e.g. '
            '`docker compose exec -it app python manage.py create_staff_user ...`.'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        username = options['username'].strip()
        email = (options.get('email') or '').strip()
        password = self._read_password()

        role = User.Role.ADMIN if options['role'] == 'admin' else User.Role.USER

        if User.objects.filter(username=username).exists():
            raise CommandError(f'User {username!r} already exists.')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=role,
        )
        if role == User.Role.ADMIN:
            user.is_staff = True
            user.save(update_fields=['is_staff'])

        self.stdout.write(self.style.SUCCESS(f'Created user {username} ({role}).'))
