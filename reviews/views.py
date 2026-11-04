from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Book
from common.permissions import IsAdmin, IsModerator
from notifications.services import notify

from .models import Review
from .serializers import ModerationReviewSerializer, ReviewInputSerializer


class BookReviews(APIView):
    """Отзывы книги: публичные (без скрытых) + собственный отзыв пользователя."""
    permission_classes = [AllowAny]
    MAX = 100

    def get(self, request, pk):
        book = get_object_or_404(Book, pk=pk, status=Book.Status.APPROVED)
        u = request.user if request.user.is_authenticated else None
        qs = Review.objects.filter(book=book, is_hidden=False).select_related('user').order_by('-updated_at')
        items = [{'id': r.id, 'user': r.user.username, 'score': float(r.score), 'text': r.text,
                  'is_mine': bool(u and r.user_id == u.id)} for r in qs[:self.MAX]]
        mine = Review.objects.filter(book=book, user=u).first() if u else None
        return Response({'results': items, 'count': qs.count(),
                         'my_review': {'score': float(mine.score), 'text': mine.text, 'is_hidden': mine.is_hidden} if mine else None})


class ReviewPut(APIView):
    def put(self, request, pk):
        book = get_object_or_404(Book, pk=pk, status=Book.Status.APPROVED)
        s = ReviewInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        review, created = Review.objects.update_or_create(  # одна рецензия на пару пользователь/книга; is_hidden не трогаем
            user=request.user, book=book,
            defaults={'score': s.validated_data['score'], 'text': s.validated_data.get('text', '')})
        return Response({'score': float(review.score), 'text': review.text, 'is_hidden': review.is_hidden,
                         'created': created}, status=201 if created else 200)

    def delete(self, request, pk):  # пользователь удаляет только свой отзыв
        deleted, _ = Review.objects.filter(user=request.user, book_id=pk).delete()
        if not deleted:
            raise NotFound('У вас нет отзыва на эту книгу.')
        return Response(status=204)


class ModerationReviews(generics.ListAPIView):
    permission_classes = [IsModerator]
    serializer_class = ModerationReviewSerializer
    queryset = Review.objects.select_related('user', 'book').order_by('-created_at')


class ModerationReviewDetail(generics.RetrieveUpdateDestroyAPIView):
    http_method_names = ['patch', 'delete', 'options']  # модератор скрывает, удаляет только администратор

    def get_permissions(self):
        return [IsAdmin()] if self.request.method == 'DELETE' else [IsModerator()]

    serializer_class = ModerationReviewSerializer

    def perform_update(self, serializer):
        was_hidden = serializer.instance.is_hidden
        review = serializer.save()
        if review.is_hidden and not was_hidden:
            notify(review.user, 'review_hidden', 'Ваш отзыв скрыт модератором', f'Отзыв на «{review.book.title}» больше не виден другим участникам.', f'#/book/{review.book_id}')
    queryset = Review.objects.select_related('user', 'book')
