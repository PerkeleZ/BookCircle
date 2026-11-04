from datetime import datetime, time, timedelta

from django.db.models import Count
from django.db.models.functions import TruncWeek
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from catalog.models import Book, BookEdit
from common.cache import cached
from common.permissions import IsModerator
from exchange.models import Copy, Loan
from meetings.models import Meeting
from reviews.models import Review


def weekly(qs, field, weeks=8):
    """Количество записей по неделям за последние `weeks` недель (пустые недели = 0)."""
    today = timezone.localdate()
    monday = today - timedelta(days=today.weekday())
    starts = [monday - timedelta(days=7 * i) for i in range(weeks - 1, -1, -1)]
    since = timezone.make_aware(datetime.combine(starts[0], time.min))
    rows = qs.filter(**{f'{field}__gte': since}).annotate(w=TruncWeek(field)).values('w').annotate(n=Count('id'))
    by_week = {timezone.localtime(r['w']).date(): r['n'] for r in rows}
    return [{'week': d.isoformat(), 'count': by_week.get(d, 0)} for d in starts]


def staff_stats():
    now = timezone.now()
    return {
        'users': {'total': User.objects.filter(is_active=True).count(), 'new_7d': User.objects.filter(date_joined__gte=now - timedelta(days=7)).count()},
        'books': {'approved': Book.objects.filter(status='approved').count(), 'pending': Book.objects.filter(status='pending').count(),
                  'hidden': Book.objects.filter(status='hidden').count(), 'edits_pending': BookEdit.objects.filter(status='pending').count()},
        'copies': {'total': Copy.objects.count(), 'active': Copy.objects.filter(is_active=True).count()},
        'loans': {'on_hand': Loan.objects.filter(status='handed_over').count(),
                  'overdue': Loan.objects.filter(status='handed_over', requested_return_date__lt=timezone.localdate()).count(),
                  'requested_30d': Loan.objects.filter(created_at__gte=now - timedelta(days=30)).count(),
                  'returned_total': Loan.objects.filter(status='returned').count()},
        'meetings_upcoming': Meeting.objects.filter(starts_at__gte=now, is_cancelled=False).count(),
        'reviews_total': Review.objects.count(),
        'series': {'new_users': weekly(User.objects.all(), 'date_joined'), 'loans': weekly(Loan.objects.all(), 'created_at')},
    }


class StaffStats(APIView):
    """Панель показателей для модераторов и администраторов (кэш 60 с)."""
    permission_classes = [IsModerator]

    def get(self, request):
        return Response(cached('stats', 'staff', 60, staff_stats))


class PublicStats(APIView):
    """Публичные цифры для главной страницы (кэш 5 минут)."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(cached('stats', 'public', 300, lambda: {
            'books': Book.objects.filter(status='approved').count(),
            'members': User.objects.filter(is_active=True).count(),
            'exchanges': Loan.objects.filter(status__in=['handed_over', 'returned']).count(),
            'reviews': Review.objects.filter(is_hidden=False).count(),
        }))
