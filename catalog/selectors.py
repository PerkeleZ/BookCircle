from django.apps import apps
from django.db.models import Avg, Count, FloatField, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from common.constants import LOAN_ACTIVE

from .models import Book


def _agg(qs, expr):
    """Скалярный подзапрос «агрегат по книге»."""
    return qs.order_by().values('book').annotate(v=expr).values('v')


def book_qs(public=True):
    """Книги с агрегатами (рейтинг, свободные экземпляры, прочитано за месяц).

    Агрегаты — коррелированные подзапросы, а не JOIN-ы: JOIN копий, передач, отзывов и чтения перемножал бы строки,
    и стоимость росла бы мультипликативно. Подзапросы считаются только для строк текущей страницы (после LIMIT) и
    используют индексы по book_id. Чужие модели берутся через реестр приложений — каталог их не импортирует."""
    Review, Copy = apps.get_model('reviews', 'Review'), apps.get_model('exchange', 'Copy')
    Entry = apps.get_model('reading', 'ReadingEntry')
    now = timezone.localdate()
    int_ = IntegerField()
    avg = _agg(Review.objects.filter(book=OuterRef('pk'), is_hidden=False), Avg('score'))  # скрытые отзывы не учитываются
    total = _agg(Copy.objects.filter(book=OuterRef('pk'), is_active=True), Count('pk'))
    busy = _agg(Copy.objects.filter(book=OuterRef('pk'), loans__status__in=LOAN_ACTIVE), Count('pk', distinct=True))
    month = _agg(Entry.objects.filter(book=OuterRef('pk'), status='done', finished_at__year=now.year,
                                      finished_at__month=now.month), Count('pk'))
    qs = Book.objects.select_related('created_by').annotate(
        avg_rating=Subquery(avg, output_field=FloatField()),
        total=Coalesce(Subquery(total, output_field=int_), Value(0)),
        busy=Coalesce(Subquery(busy, output_field=int_), Value(0)),
        read_month=Coalesce(Subquery(month, output_field=int_), Value(0)),
    )
    if public:  # на сайте видны только одобренные модератором книги
        qs = qs.filter(status=Book.Status.APPROVED)
    return qs.order_by('title')
