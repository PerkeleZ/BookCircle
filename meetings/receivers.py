from django.dispatch import receiver

from catalog.signals import book_deleting

from .models import Meeting


@receiver(book_deleting)
def on_book_deleting(sender, book, **kwargs):
    Meeting.objects.filter(book=book).update(book=None)  # встречи остаются, но без привязки к книге
