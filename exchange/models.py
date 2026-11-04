from django.conf import settings
from django.db import models
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone


class CopyQuerySet(models.QuerySet):
    def with_busy(self):
        return self.annotate(busy=Exists(Loan.objects.filter(copy=OuterRef('pk'), status__in=Loan.ACTIVE)))


class Copy(models.Model):
    class Condition(models.TextChoices):
        NEW = 'new', 'Новое'
        GOOD = 'good', 'Хорошее'
        FAIR = 'fair', 'Среднее'
        WORN = 'worn', 'Потрёпанное'

    book = models.ForeignKey('catalog.Book', on_delete=models.PROTECT, related_name='copies')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='copies')
    condition = models.CharField(max_length=8, choices=Condition.choices, default=Condition.GOOD)
    pickup_place = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True, db_index=True)
    objects = CopyQuerySet.as_manager()

    class Meta:
        indexes = [models.Index(fields=['owner', 'is_active'])]


class Loan(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает'
        ACCEPTED = 'accepted', 'Принята'
        REJECTED = 'rejected', 'Отклонена'
        CANCELLED = 'cancelled', 'Отменена'
        HANDED_OVER = 'handed_over', 'Передана'
        RETURNED = 'returned', 'Возвращена'

    ACTIVE = (Status.ACCEPTED, Status.HANDED_OVER)

    # PROTECT: история обменов не должна исчезать при удалении экземпляра или пользователя
    copy = models.ForeignKey(Copy, on_delete=models.PROTECT, related_name='loans')
    borrower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='loans')
    requested_return_date = models.DateField()
    last_reminded_on = models.DateField(null=True, blank=True)  # когда в последний раз напоминали о просрочке
    borrower_phone = models.CharField(max_length=20, blank=True)  # контакт получателя, виден владельцу
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    handed_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['borrower', 'status'])]
        constraints = [  # не более одной принятой/активной передачи на экземпляр — гарантия на уровне БД
            models.UniqueConstraint(fields=['copy'], condition=Q(status__in=['accepted', 'handed_over']),
                                    name='one_active_loan_per_copy'),
        ]

    @property
    def is_overdue(self):
        return self.status == self.Status.HANDED_OVER and self.requested_return_date < timezone.localdate()
