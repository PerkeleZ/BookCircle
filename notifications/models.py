from django.conf import settings
from django.db import models


class Notification(models.Model):
    """Уведомление пользователя: показывается на сайте (колокольчик) и, если включено, дублируется на email."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=30)  # loan_request, loan_overdue, book_approved, meeting_cancelled …
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=200, blank=True)  # маршрут сайта, например #/loans?box=incoming
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    emailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['user', 'is_read', '-created_at'])]
