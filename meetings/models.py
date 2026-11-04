from django.conf import settings
from django.db import models
from django.db.models import Q


class Meeting(models.Model):
    """Книжная встреча: обсуждение книги в назначенное время и месте."""
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    book = models.ForeignKey('catalog.Book', on_delete=models.PROTECT, null=True, blank=True, related_name='meetings')
    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='organized_meetings')
    starts_at = models.DateTimeField(db_index=True)
    place = models.CharField(max_length=200)
    capacity = models.PositiveIntegerField(null=True, blank=True)  # None — без ограничения
    is_cancelled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['starts_at']
        constraints = [models.CheckConstraint(condition=Q(capacity__isnull=True) | Q(capacity__gte=1),
                                              name='meeting_capacity_positive')]


class MeetingParticipant(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='meeting_entries')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['meeting', 'user'], name='one_participation_per_meeting')]
