from django.dispatch import receiver

from catalog.signals import book_deleting

from .models import ReadingEntry


@receiver(book_deleting)
def on_book_deleting(sender, book, **kwargs):
    ReadingEntry.objects.filter(book=book).delete()
