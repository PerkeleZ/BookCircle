from django.core.management.base import BaseCommand

from exchange.services import remind_overdue


class Command(BaseCommand):
    help = 'Отправить напоминания о просроченных возвратах (то же, что ежедневная задача Celery; можно вызывать из cron).'

    def handle(self, *args, **options):
        self.stdout.write(f'Напоминаний создано: {remind_overdue()}')
