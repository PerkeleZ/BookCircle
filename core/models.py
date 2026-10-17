from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from decimal import Decimal


# Жанры по умолчанию (модератор может добавлять и другие — поле Book.genre свободное)
DEFAULT_GENRES = ['Роман', 'Классика', 'Фантастика', 'Детектив', 'Ужасы', 'Научпоп', 'Поэзия', 'История',
                  'Учебники и пособия по IT']


class User(AbstractUser):
    class Role(models.TextChoices):
        PARTICIPANT = 'participant', 'Участник'
        MODERATOR = 'moderator', 'Модератор'
        ADMIN = 'admin', 'Администратор'

    email = models.EmailField(blank=True)
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.PARTICIPANT)
    bio = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    google_sub = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)  # привязка к Google
    google_email = models.EmailField(blank=True, editable=False)

    @property
    def is_moderator(self):
        return self.role in (self.Role.MODERATOR, self.Role.ADMIN)

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)


class Book(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'На модерации'
        APPROVED = 'approved', 'Одобрена'
        REJECTED = 'rejected', 'Отклонена'
        HIDDEN = 'hidden', 'Скрыта'

    title = models.CharField(max_length=255, db_index=True)
    author = models.CharField(max_length=255, db_index=True)
    genre = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True)
    cover = models.URLField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.APPROVED, db_index=True)
    created_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_books')
    reject_reason = models.CharField(max_length=300, blank=True)
    # нижний регистр для поиска (SQLite не умеет регистронезависимый поиск по кириллице)
    search_text = models.CharField(max_length=512, editable=False, db_index=True, default='')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['title', 'author'], condition=~Q(status='rejected'), name='uniq_live_book_title_author')]

    def save(self, *args, **kwargs):
        self.search_text = f'{self.title} {self.author}'.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.title} — {self.author}'


class CopyQuerySet(models.QuerySet):
    def with_busy(self):
        return self.annotate(busy=Exists(Loan.objects.filter(copy=OuterRef('pk'), status__in=Loan.ACTIVE)))


class Copy(models.Model):
    class Condition(models.TextChoices):
        NEW = 'new', 'Новое'
        GOOD = 'good', 'Хорошее'
        FAIR = 'fair', 'Среднее'
        WORN = 'worn', 'Потрёпанное'

    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name='copies')
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name='copies')
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
    borrower = models.ForeignKey(User, on_delete=models.PROTECT, related_name='loans')
    requested_return_date = models.DateField()
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


class ReadingEntry(models.Model):
    class Status(models.TextChoices):
        WANT = 'want', 'Хочу прочитать'
        READING = 'reading', 'Читаю'
        DONE = 'done', 'Прочитал'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='entries')
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name='entries')
    status = models.CharField(max_length=8, choices=Status.choices)
    finished_at = models.DateField(null=True, blank=True, db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'book'], name='one_entry_per_user_book')]


class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name='reviews')
    score = models.DecimalField(max_digits=2, decimal_places=1, validators=[MinValueValidator(Decimal('0.5')), MaxValueValidator(Decimal('5.0'))])  # шаг 0,5
    text = models.TextField(blank=True)
    is_hidden = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'book'], name='one_review_per_user_book'),
            models.CheckConstraint(condition=Q(score__gte=Decimal('0.5'), score__lte=Decimal('5.0')), name='review_score_1_5'),
        ]


class PasswordResetCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reset_codes')
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    attempts = models.PositiveSmallIntegerField(default=0)


class Meeting(models.Model):
    """Книжная встреча: обсуждение книги в назначенное время и месте."""
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    book = models.ForeignKey(Book, on_delete=models.PROTECT, null=True, blank=True, related_name='meetings')
    organizer = models.ForeignKey(User, on_delete=models.PROTECT, related_name='organized_meetings')
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='meeting_entries')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['meeting', 'user'], name='one_participation_per_meeting')]


class ReadingGoal(models.Model):
    """Цель чтения: сколько книг прочитать за год (month=0) или за конкретный месяц (1–12)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='goals')
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField(default=0)
    target = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'year', 'month'], name='one_goal_per_period'),
            models.CheckConstraint(condition=Q(month__gte=0, month__lte=12), name='goal_month_0_12'),
            models.CheckConstraint(condition=Q(target__gte=1, target__lte=365), name='goal_target_1_365'),
        ]


class BookEdit(models.Model):
    """Предложенная пользователем правка книги: вступает в силу после одобрения модератором."""
    class Status(models.TextChoices):
        PENDING = 'pending', 'На модерации'
        APPROVED = 'approved', 'Одобрена'
        REJECTED = 'rejected', 'Отклонена'

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='edits')
    proposed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='book_edits')
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    genre = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    cover = models.URLField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    reject_reason = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        constraints = [models.UniqueConstraint(fields=['book', 'proposed_by'], condition=Q(status='pending'),
                                               name='one_pending_edit_per_user_book')]
