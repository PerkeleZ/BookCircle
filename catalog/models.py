from django.conf import settings
from django.db import models
from django.db.models import Q


DEFAULT_GENRES = ['Роман', 'Классика', 'Фантастика', 'Детектив', 'Ужасы', 'Научпоп', 'Поэзия', 'История',
                  'Учебники и пособия по IT']


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
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_books')
    reject_reason = models.CharField(max_length=300, blank=True)
    # нижний регистр для поиска (SQLite не умеет регистронезависимый поиск по кириллице)
    search_text = models.CharField(max_length=512, editable=False, db_index=True, default='')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['title', 'author'], condition=~Q(status='rejected'), name='uniq_live_book_title_author')]
        indexes = [models.Index(fields=['status', 'title'])]

    def save(self, *args, **kwargs):
        self.search_text = f'{self.title} {self.author}'.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.title} — {self.author}'


class BookEdit(models.Model):
    """Предложенная пользователем правка книги: вступает в силу после одобрения модератором."""
    class Status(models.TextChoices):
        PENDING = 'pending', 'На модерации'
        APPROVED = 'approved', 'Одобрена'
        REJECTED = 'rejected', 'Отклонена'

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='edits')
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='book_edits')
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
