from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import PasswordResetCode
from catalog.models import Book, BookEdit
from common.constants import LOAN_ACTIVE
from common.exceptions import Conflict
from exchange.models import Copy, Loan
from meetings.models import Meeting, MeetingParticipant
from notifications.models import Notification
from reading.models import ReadingEntry, ReadingGoal
from reviews.models import Review


class ExportData(APIView):
    """Право на переносимость данных: все данные пользователя одним JSON-файлом."""

    def get(self, request):
        u = request.user
        loans = Loan.objects.select_related('copy__book', 'copy__owner', 'borrower')
        data = {
            'exported_at': timezone.now().isoformat(),
            'profile': {'username': u.username, 'email': u.email, 'phone': u.phone, 'bio': u.bio, 'role': u.role,
                        'notify_email': u.notify_email, 'google_email': u.google_email, 'joined': u.date_joined.isoformat()},
            'copies': [{'book': c.book.title, 'condition': c.condition, 'pickup_place': c.pickup_place, 'is_active': c.is_active}
                       for c in Copy.objects.filter(owner=u).select_related('book')],
            'loans_as_borrower': [{'book': l.copy.book.title, 'owner': l.copy.owner.username, 'status': l.status, 'phone_given': l.borrower_phone,
                                   'due': l.requested_return_date.isoformat()} for l in loans.filter(borrower=u)],
            'loans_as_owner': [{'book': l.copy.book.title, 'borrower': l.borrower.username, 'status': l.status,
                                'due': l.requested_return_date.isoformat()} for l in loans.filter(copy__owner=u)],
            'reviews': [{'book': r.book.title, 'score': float(r.score), 'text': r.text, 'hidden': r.is_hidden}
                        for r in Review.objects.filter(user=u).select_related('book')],
            'reading': [{'book': e.book.title, 'status': e.status, 'finished_at': e.finished_at}
                        for e in ReadingEntry.objects.filter(user=u).select_related('book')],
            'goals': [{'year': g.year, 'month': g.month or None, 'target': g.target} for g in ReadingGoal.objects.filter(user=u)],
            'meetings_organized': [{'title': m.title, 'starts_at': m.starts_at.isoformat(), 'cancelled': m.is_cancelled} for m in Meeting.objects.filter(organizer=u)],
            'meetings_joined': [{'title': p.meeting.title, 'starts_at': p.meeting.starts_at.isoformat()} for p in MeetingParticipant.objects.filter(user=u).select_related('meeting')],
            'submitted_books': [{'title': b.title, 'author': b.author, 'status': b.status} for b in Book.objects.filter(created_by=u)],
            'book_edits': [{'book': e.book.title, 'status': e.status} for e in BookEdit.objects.filter(proposed_by=u).select_related('book')],
            'notifications': [{'title': n.title, 'body': n.body, 'created_at': n.created_at.isoformat()} for n in Notification.objects.filter(user=u)],
        }
        response = Response(data)
        response['Content-Disposition'] = f'attachment; filename="bookcircle-data-{u.username}.json"'
        return response


class EraseAccount(APIView):
    """Право на удаление: персональные данные стираются, а история обменов остаётся у других участников
    с обезличенным именем. Нельзя, пока есть принятые или переданные книги."""

    def post(self, request):
        u = request.user
        if u.has_usable_password() and not u.check_password(str(request.data.get('password') or '')):
            raise ValidationError({'password': ['Неверный пароль.']})
        if str(request.data.get('confirm') or '').strip() != u.username:
            raise ValidationError({'confirm': ['Введите свой логин для подтверждения.']})
        mine = Q(borrower=u) | Q(copy__owner=u)
        with transaction.atomic():
            if Loan.objects.filter(mine, status__in=LOAN_ACTIVE).exists():
                raise Conflict('У вас есть незавершённые обмены — завершите их перед удалением аккаунта.')
            Loan.objects.filter(mine, status='pending').update(status='cancelled')
            for c in Copy.objects.filter(owner=u):
                if c.loans.exists():
                    c.is_active = False  # история обменов других участников сохраняется
                    c.save(update_fields=['is_active'])
                else:
                    c.delete()
            Meeting.objects.filter(organizer=u, starts_at__gt=timezone.now(), is_cancelled=False).update(is_cancelled=True)
            for model, field in ((Review, 'user'), (ReadingEntry, 'user'), (ReadingGoal, 'user'), (MeetingParticipant, 'user'),
                                 (BookEdit, 'proposed_by'), (Notification, 'user'), (PasswordResetCode, 'user'), (Token, 'user')):
                model.objects.filter(**{field: u}).delete()
            u.username, u.email, u.phone, u.bio = f'deleted-{u.id}', '', '', ''
            u.google_sub, u.google_email, u.is_active = None, '', False
            u.set_unusable_password()
            u.save()
        return Response(status=204)
