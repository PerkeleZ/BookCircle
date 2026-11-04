import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Notification

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def deliver_email(self, notification_id):
    n = Notification.objects.select_related('user').filter(pk=notification_id).first()
    if not n or n.emailed_at or not n.user.email:
        return
    link = f'\n\nОткрыть: {settings.FRONTEND_URL}/{n.link}' if n.link else ''
    try:
        send_mail(f'BookCircle: {n.title}', f'{n.body}{link}\n\nОтключить письма можно в профиле.', settings.DEFAULT_FROM_EMAIL, [n.user.email])
    except Exception as exc:  # noqa: BLE001
        logger.warning('Письмо не отправлено (%s), повтор', type(exc).__name__)
        raise self.retry(exc=exc)
    n.emailed_at = timezone.now()
    n.save(update_fields=['emailed_at'])
