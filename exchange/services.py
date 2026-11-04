import logging

from django.utils import timezone

from notifications.services import notify

from .models import Loan

logger = logging.getLogger(__name__)


def loan_requested(loan):
    book = loan.copy.book.title
    notify(loan.copy.owner, 'loan_request', f'Новый запрос на «{book}»',
           f'{loan.borrower.username} просит книгу до {loan.requested_return_date:%d.%m.%Y}. Телефон: {loan.borrower_phone}.',
           '#/loans?box=incoming')


def loan_changed(loan, action):
    """Уведомления о смене статуса передачи (вызывается после успешного перехода)."""
    book, owner, borrower = loan.copy.book.title, loan.copy.owner, loan.borrower
    texts = {
        'accept': (borrower, 'loan_accepted', f'Запрос на «{book}» принят', f'{owner.username} принял(а) запрос. Договоритесь о передаче.', '#/loans?box=outgoing'),
        'reject': (borrower, 'loan_rejected', f'Запрос на «{book}» отклонён', f'{owner.username} отклонил(а) запрос.', '#/loans?box=outgoing'),
        'hand-over': (borrower, 'loan_handed_over', f'Книга «{book}» передана вам', f'Верните её до {loan.requested_return_date:%d.%m.%Y}.', '#/loans?box=active'),
        'return': (borrower, 'loan_returned', f'Возврат «{book}» подтверждён', 'Спасибо! Книга снова доступна в клубе.', '#/loans?box=outgoing'),
    }
    if action in texts:
        notify(*texts[action])
    elif action == 'cancel':  # отменить может любая сторона — сообщаем обеим
        notify(owner, 'loan_cancelled', f'Обмен «{book}» отменён', f'Запрос от {borrower.username} отменён.', '#/loans?box=incoming')
        notify(borrower, 'loan_cancelled', f'Обмен «{book}» отменён', f'Обмен с {owner.username} отменён.', '#/loans?box=outgoing')


def remind_overdue(today=None, email=True):
    """Напоминание о просрочке обеим сторонам — не чаще раза в день на передачу. Возвращает число передач."""
    today = today or timezone.localdate()
    loans = (Loan.objects.filter(status=Loan.Status.HANDED_OVER, requested_return_date__lt=today)
             .exclude(last_reminded_on=today).select_related('copy__book', 'copy__owner', 'borrower'))
    n = 0
    for loan in loans:
        days, book = (today - loan.requested_return_date).days, loan.copy.book.title
        notify(loan.borrower, 'loan_overdue', f'Просрочен возврат «{book}»', f'Верните книгу владельцу {loan.copy.owner.username}: просрочка {days} дн.', '#/loans?box=active', email=email)
        notify(loan.copy.owner, 'loan_overdue', f'«{book}» не возвращена вовремя', f'{loan.borrower.username} задерживает книгу {days} дн. Телефон: {loan.borrower_phone}.', '#/loans?box=active', email=email)
        loan.last_reminded_on = today
        loan.save(update_fields=['last_reminded_on'])
        n += 1
    return n
