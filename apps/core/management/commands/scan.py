"""Сводка нагрузки и дискового пространства (см. docs/SPEC п. 16.1)."""

import shutil

import psutil
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Показать CPU/RAM и использование диска (для SSH / консоли).'

    def handle(self, *args, **options):
        cpu = psutil.cpu_percent(interval=0.3)
        vm = psutil.virtual_memory()
        du = shutil.disk_usage('/')

        self.stdout.write(f'CPU: {cpu}%')
        self.stdout.write(
            f'Memory: {vm.percent}% used ({vm.used // (1024 ** 3)} GiB / {vm.total // (1024 ** 3)} GiB)'
        )
        self.stdout.write(
            f'Disk /: {du.used // (1024 ** 3)} GiB used / {du.total // (1024 ** 3)} GiB total '
            f'({100 * du.used // du.total}%)'
        )
