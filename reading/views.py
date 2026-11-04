from collections import Counter

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Book
from catalog.selectors import book_qs
from catalog.serializers import BookSerializer
from reviews.models import Review

from .models import ReadingEntry, ReadingGoal
from .serializers import GoalInputSerializer, ReadingInputSerializer, ReadingSerializer


class ReadingList(APIView):
    def get(self, request):
        qs = ReadingEntry.objects.filter(user=request.user).select_related('book').order_by('status', 'book__title')
        t = timezone.localdate()
        n = qs.filter(status='done', finished_at__year=t.year, finished_at__month=t.month).count()
        return Response({'results': ReadingSerializer(qs, many=True).data, 'finished_this_month': n})


class ReadingDetail(APIView):
    def get(self, request, book_id):
        e = ReadingEntry.objects.filter(user=request.user, book_id=book_id).first()
        return Response({'status': e.status if e else None, 'finished_at': e.finished_at if e else None})

    def put(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id, status=Book.Status.APPROVED)
        s = ReadingInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        status = s.validated_data['status']
        finished = None
        if status == ReadingEntry.Status.DONE:
            old = ReadingEntry.objects.filter(user=request.user, book=book).first()
            finished = s.validated_data.get('finished_at') or (old.finished_at if old else None) or timezone.localdate()
        entry, _ = ReadingEntry.objects.update_or_create(
            user=request.user, book=book, defaults={'status': status, 'finished_at': finished})
        return Response(ReadingSerializer(entry).data)


def goal_payload(user, year, month):
    g = ReadingGoal.objects.filter(user=user, year=year, month=month).first()
    if not g:
        return None
    done_qs = ReadingEntry.objects.filter(user=user, status='done', finished_at__year=year)
    if month:
        done_qs = done_qs.filter(finished_at__month=month)
    done = done_qs.count()
    return {'id': g.id, 'period': 'month' if month else 'year', 'year': year, 'month': month or None,
            'target': g.target, 'done': done, 'left': max(0, g.target - done),
            'percent': min(100, round(done * 100 / g.target)), 'achieved': done >= g.target}


def goals_data(user):
    t = timezone.localdate()
    return {'year': goal_payload(user, t.year, 0), 'month': goal_payload(user, t.year, t.month)}


class GoalView(APIView):
    def get(self, request):
        return Response(goals_data(request.user))

    def put(self, request):
        s = GoalInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        t = timezone.localdate()
        month = t.month if s.validated_data['period'] == 'month' else 0
        ReadingGoal.objects.update_or_create(user=request.user, year=t.year, month=month,
                                             defaults={'target': s.validated_data['target']})
        return Response(goals_data(request.user))


class GoalDelete(APIView):
    def delete(self, request, period):
        if period not in ('year', 'month'):
            raise NotFound()
        t = timezone.localdate()
        ReadingGoal.objects.filter(user=request.user, year=t.year, month=t.month if period == 'month' else 0).delete()
        return Response(status=204)


class Recommendations(APIView):
    def get(self, request):
        weights, seen = Counter(), set()
        for e in ReadingEntry.objects.filter(user=request.user).select_related('book'):
            seen.add(e.book_id)  # то, что уже в списке чтения, не рекомендуем
            weights[e.book.genre] += {'done': 2, 'reading': 1, 'want': 1}[e.status]
        for r in Review.objects.filter(user=request.user).select_related('book'):
            seen.add(r.book_id)
            weights[r.book.genre] += 2 if r.score >= 4 else (-1 if r.score <= 2 else 0)
        top = [g for g, w in weights.most_common() if w > 0][:3]
        qs = book_qs().exclude(pk__in=seen)
        if top:
            books = sorted(qs.filter(genre__in=top),
                           key=lambda b: (-weights[b.genre], -(b.avg_rating or 0), -(b.total - b.busy)))
            reason = lambda b: f'Вам нравится жанр «{b.genre}»'
        else:  # «холодный старт»: пока нет данных о вкусах — самое высоко оценённое в клубе
            books = sorted(qs, key=lambda b: (-(b.avg_rating or 0), -b.read_month, b.title))
            reason = lambda b: 'Популярно в клубе'
        results = [{**BookSerializer(b).data, 'reason': reason(b)} for b in books[:8]]
        return Response({'genres': [{'genre': g, 'score': weights[g]} for g in top], 'results': results})
