from django.dispatch import receiver

from catalog.signals import book_deleting
from common.constants import LOAN_ACTIVE
from common.exceptions import Conflict

from .models import Copy, Loan


@receiver(book_deleting)
def on_book_deleting(sender, book, **kwargs):
    if Loan.objects.filter(copy__book=book, status__in=LOAN_ACTIVE).exists():
        raise Conflict('У книги есть принятые или переданные экземпляры — дождитесь возврата.')
    Loan.objects.filter(copy__book=book).delete()  # история обменов удаляется явно, а не каскадом
    Copy.objects.filter(book=book).delete()
