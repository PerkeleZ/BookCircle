from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Book
from common.exceptions import Bad, Conflict
from common.permissions import IsOwner

from . import services
from .models import Copy, Loan
from .serializers import CopySerializer, LoanCreateSerializer, LoanSerializer

S = Loan.Status


class BookCopies(APIView):
    """Экземпляры книги, доступные в клубе (страница книги)."""
    permission_classes = [AllowAny]

    def get(self, request, pk):
        book = get_object_or_404(Book, pk=pk, status=Book.Status.APPROVED)
        qs = Copy.objects.with_busy().select_related('book', 'owner').filter(book=book, is_active=True)
        return Response({'results': CopySerializer(qs, many=True).data})


class CopyList(generics.ListCreateAPIView):
    serializer_class = CopySerializer

    def get_queryset(self):
        qs = Copy.objects.with_busy().select_related('book', 'owner').order_by('-id')
        if self.request.query_params.get('mine'):
            return qs.filter(owner=self.request.user)
        return qs.filter(is_active=True, book__status=Book.Status.APPROVED)

    def perform_create(self, s):
        s.save(owner=self.request.user)


class CopyDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CopySerializer
    permission_classes = [IsAuthenticated, IsOwner]
    queryset = Copy.objects.with_busy().select_related('book', 'owner')

    def perform_update(self, s):
        with transaction.atomic():
            copy = Copy.objects.select_for_update().get(pk=s.instance.pk)
            if s.validated_data.get('is_active') is False and copy.loans.filter(status__in=Loan.ACTIVE).exists():
                raise Conflict('Экземпляр передан или забронирован — скрыть его можно после возврата.')
            s.save()
            if not s.instance.is_active:  # скрытый экземпляр: ожидающие запросы отменяются
                copy.loans.filter(status=S.PENDING).update(status=S.CANCELLED)

    def perform_destroy(self, inst):
        if inst.loans.exists():
            raise Conflict('У экземпляра есть история обменов — скройте его вместо удаления.')
        inst.delete()


class LoanList(generics.ListAPIView):
    serializer_class = LoanSerializer

    def get_queryset(self):
        qs = Loan.objects.select_related('copy__book', 'copy__owner', 'borrower')
        u, box = self.request.user, self.request.query_params.get('box')
        if box == 'outgoing':
            return qs.filter(borrower=u)
        if box == 'active':  # аренда в процессе: книги «на руках» у меня или у моих заёмщиков
            return qs.filter(status=S.HANDED_OVER).filter(Q(borrower=u) | Q(copy__owner=u)).order_by('requested_return_date')
        return qs.filter(copy__owner=u)


class LoanCreate(APIView):
    def post(self, request, pk):
        s = LoanCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        with transaction.atomic():
            copy = get_object_or_404(Copy.objects.select_for_update(), pk=pk)
            if copy.owner_id == request.user.id:
                raise Bad('Нельзя запросить собственную книгу.')
            if not copy.is_active:
                raise Conflict('Этот экземпляр сейчас недоступен.')
            if copy.book.status != Book.Status.APPROVED:
                raise Conflict('Эта книга сейчас недоступна.')
            if copy.loans.filter(status__in=Loan.ACTIVE).exists():
                raise Conflict('Экземпляр сейчас занят — дождитесь возврата.')
            if copy.loans.filter(borrower=request.user, status=S.PENDING).exists():
                raise Conflict('Вы уже отправили запрос на этот экземпляр.')
            loan = Loan.objects.create(copy=copy, borrower=request.user,
                                       requested_return_date=s.validated_data['requested_return_date'],
                                       borrower_phone=s.validated_data['phone'])
        services.loan_requested(loan)
        return Response(LoanSerializer(loan).data, status=201)


RULES = {
    'accept': ({S.PENDING}, S.ACCEPTED, 'owner'),
    'reject': ({S.PENDING}, S.REJECTED, 'owner'),
    'cancel': ({S.PENDING, S.ACCEPTED}, S.CANCELLED, 'party'),
    'hand-over': ({S.ACCEPTED}, S.HANDED_OVER, 'owner'),
    'return': ({S.HANDED_OVER}, S.RETURNED, 'owner'),
}


class LoanAction(APIView):
    def post(self, request, pk, action):
        rule = RULES.get(action)
        if not rule:
            raise NotFound()
        allowed, new_status, who = rule
        with transaction.atomic():
            copy_id = get_object_or_404(Loan, pk=pk).copy_id
            copy = Copy.objects.select_for_update().select_related('owner', 'book').get(pk=copy_id)  # блокировка экземпляра
            loan = Loan.objects.select_related('borrower').get(pk=pk)
            loan.copy = copy
            uid = request.user.id
            is_owner = copy.owner_id == uid
            if (who == 'owner' and not is_owner) or (who == 'party' and not (is_owner or loan.borrower_id == uid)):
                raise PermissionDenied('Это действие вам недоступно.')
            if loan.status not in allowed:
                raise Conflict(f'Нельзя выполнить действие: статус запроса — «{loan.get_status_display()}».')
            if action == 'accept':
                if not copy.is_active:
                    raise Conflict('Экземпляр скрыт владельцем.')
                if copy.loans.filter(status__in=Loan.ACTIVE).exists():
                    raise Conflict('Этот экземпляр уже передан или забронирован другим участником.')
            loan.status = new_status
            if action == 'hand-over':
                loan.handed_at = timezone.now()
            if action == 'return':
                loan.returned_at = timezone.now()
            try:
                with transaction.atomic():
                    loan.save()
            except IntegrityError:
                raise Conflict('Этот экземпляр уже занят другим запросом.')
            if action == 'accept':  # остальные ожидающие запросы отклоняются
                copy.loans.filter(status=S.PENDING).exclude(pk=loan.pk).update(status=S.REJECTED)
        services.loan_changed(loan, action)
        return Response(LoanSerializer(loan).data)


class Alerts(APIView):
    """Книги «на руках» с просроченным или близким (≤ 2 дней) сроком возврата — для получателя и владельца."""

    def get(self, request):
        u, today = request.user, timezone.localdate()
        loans = (Loan.objects.filter(status=S.HANDED_OVER, requested_return_date__lte=today + timedelta(days=2))
                 .filter(Q(borrower=u) | Q(copy__owner=u)).select_related('copy__book', 'copy__owner', 'borrower'))
        items = []
        for l in loans:
            days_left = (l.requested_return_date - today).days
            as_borrower = l.borrower_id == u.id
            items.append({'id': l.id, 'book_id': l.copy.book_id, 'book_title': l.copy.book.title,
                          'role': 'borrower' if as_borrower else 'owner',
                          'other': l.copy.owner.username if as_borrower else l.borrower.username,
                          'other_phone': l.copy.owner.phone if as_borrower else l.borrower_phone,
                          'due': l.requested_return_date, 'days_left': days_left, 'overdue': days_left < 0})
        items.sort(key=lambda i: i['days_left'])
        return Response({'count': len(items), 'overdue': sum(i['overdue'] for i in items), 'results': items})
