import logging

from django.db import transaction

from .models import Notification

logger = logging.getLogger(__name__)


def notify(user, kind, title, body='', link='', email=True):
    """Создать уведомление; письмо уходит фоново (Celery) после фиксации транзакции."""
    if user is None or not user.is_active:
        return None
    n = Notification.objects.create(user=user, kind=kind, title=title[:160], body=body, link=link)
    if email and user.email and user.notify_email:
        transaction.on_commit(lambda: _queue_email(n.id))
    return n


def _queue_email(notification_id):
    from .tasks import deliver_email
    try:
        deliver_email.delay(notification_id)
    except Exception:  # noqa: BLE001 — недоступный брокер не должен ломать запрос пользователя
        logger.exception('Не удалось поставить письмо в очередь')
