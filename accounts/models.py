from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        PARTICIPANT = 'participant', 'Участник'
        MODERATOR = 'moderator', 'Модератор'
        ADMIN = 'admin', 'Администратор'

    email = models.EmailField(blank=True)
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.PARTICIPANT)
    bio = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    notify_email = models.BooleanField(default=True)  # дублировать уведомления на email
    google_sub = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)  # привязка к Google
    google_email = models.EmailField(blank=True, editable=False)

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_moderator(self):
        return self.role in (self.Role.MODERATOR, self.Role.ADMIN)

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)


class PasswordResetCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reset_codes')
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    attempts = models.PositiveSmallIntegerField(default=0)
