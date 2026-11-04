from celery import shared_task

from . import services


@shared_task(name='exchange.tasks.remind_overdue')
def remind_overdue():
    """Ежедневная задача (Celery beat): напоминания о просроченных возвратах."""
    return services.remind_overdue()
