from django.dispatch import receiver

from catalog.signals import book_deleting

from .models import Review


@receiver(book_deleting)
def on_book_deleting(sender, book, **kwargs):
    Review.objects.filter(book=book).delete()
