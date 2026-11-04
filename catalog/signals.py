from django.db.models.signals import post_delete, post_save
from django.dispatch import Signal, receiver

from common.cache import bump

from .models import Book

# Отправляется перед удалением книги. Другие приложения подписываются и либо запрещают удаление (Conflict),
# либо убирают свои связанные данные — каталог ничего о них не знает.
book_deleting = Signal()


@receiver([post_save, post_delete], sender=Book)
def invalidate_catalog_cache(sender, **kwargs):
    bump('catalog')
