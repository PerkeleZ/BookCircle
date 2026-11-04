from django.conf import settings
from django.db import models
from django.db.models import Q


class ReadingEntry(models.Model):
    class Status(models.TextChoices):
        WANT = 'want', 'Хочу прочитать'
        READING = 'reading', 'Читаю'
        DONE = 'done', 'Прочитал'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='entries')
    book = models.ForeignKey('catalog.Book', on_delete=models.PROTECT, related_name='entries')
    status = models.CharField(max_length=8, choices=Status.choices)
    finished_at = models.DateField(null=True, blank=True, db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'book'], name='one_entry_per_user_book')]


class ReadingGoal(models.Model):
    """Цель чтения: сколько книг прочитать за год (month=0) или за конкретный месяц (1–12)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='goals')
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField(default=0)
    target = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'year', 'month'], name='one_goal_per_period'),
            models.CheckConstraint(condition=Q(month__gte=0, month__lte=12), name='goal_month_0_12'),
            models.CheckConstraint(condition=Q(target__gte=1, target__lte=365), name='goal_target_1_365'),
        ]
