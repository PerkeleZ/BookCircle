from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.cache import cached
from common.exceptions import Bad, Conflict
from common.permissions import IsModerator
from notifications.services import notify

from .models import DEFAULT_GENRES, Book, BookEdit
from .selectors import book_qs
from .serializers import EDIT_FIELDS, BookEditSerializer, BookSerializer
from .signals import book_deleting


class BookList(generics.ListCreateAPIView):
    serializer_class = BookSerializer

    def get_permissions(self):
        return [AllowAny()] if self.request.method in SAFE_METHODS else [IsAuthenticated()]

    def get_queryset(self):
        p = self.request.query_params
        qs = book_qs()
        if q := p.get('search', '').strip().lower():
            qs = qs.filter(search_text__contains=q)
        if g := p.get('genre'):
            qs = qs.filter(genre=g)
        return qs

    def perform_create(self, s):  # любой участник может предложить книгу; публикуется после модерации
        u = self.request.user
        s.save(created_by=u, status=Book.Status.APPROVED if u.is_moderator else Book.Status.PENDING)


class BookDetail(generics.RetrieveUpdateDestroyAPIView):
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_permissions(self):
        return [AllowAny()] if self.request.method in SAFE_METHODS else [IsAuthenticated()]

    def get_queryset(self):
        return book_qs(public=False)

    def get_serializer_class(self):
        return BookSerializer

    def get_object(self):
        book, u = super().get_object(), self.request.user
        visible = book.status == Book.Status.APPROVED or (u.is_authenticated and (
            u.is_moderator or (book.created_by_id == u.id and book.status in (Book.Status.PENDING, Book.Status.REJECTED))))
        if not visible:
            raise NotFound()
        return book

    def perform_update(self, s):
        u, book = self.request.user, s.instance
        if u.is_moderator:
            s.save()
        elif book.created_by_id == u.id and book.status in (Book.Status.PENDING, Book.Status.REJECTED):
            s.save(status=Book.Status.PENDING, reject_reason='')  # правка отклонённой книги возвращает её на модерацию
        else:
            raise PermissionDenied('Предложите правку: она появится на сайте после проверки модератором.')

    def perform_destroy(self, book):
        u = self.request.user
        own_draft = book.created_by_id == u.id and book.status in (Book.Status.PENDING, Book.Status.REJECTED)
        if not (u.is_admin or own_draft):
            raise PermissionDenied('Удалять книги может только администратор.')
        with transaction.atomic():
            book_deleting.send(sender=Book, book=book)  # другие приложения проверяют и чистят свои данные (или запрещают удаление)
            book.delete()


class BookVisibility(APIView):
    permission_classes = [IsModerator]

    def post(self, request, pk, hide):
        book = get_object_or_404(Book, pk=pk)
        if hide:
            if book.status != Book.Status.APPROVED:
                raise Conflict('Скрыть можно только опубликованную книгу.')
            book.status = Book.Status.HIDDEN
        else:
            if book.status != Book.Status.HIDDEN:
                raise Conflict('Эта книга не скрыта.')
            book.status = Book.Status.APPROVED
        book.save(update_fields=['status'])
        return Response({'status': book.status})


class BookOptions(APIView):
    """Книги для выпадающих списков («Моя полка», встречи). Без параметров — все одобренные (кэшируется);
    с ?q= — серверный поиск на 50 записей (для больших каталогов)."""

    def get(self, request):
        fields = ('id', 'title', 'author', 'genre')
        q = request.query_params.get('q', '').strip().lower()
        if q:
            rows = list(Book.objects.filter(status=Book.Status.APPROVED, search_text__contains=q).order_by('title').values(*fields)[:50])
        else:
            rows = cached('catalog', 'options', 300, lambda: list(
                Book.objects.filter(status=Book.Status.APPROVED).order_by('title').values(*fields)))
        return Response({'results': rows})


class GenreList(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        def build():
            used = Book.objects.filter(status=Book.Status.APPROVED).order_by().values_list('genre', flat=True).distinct()
            return DEFAULT_GENRES + sorted(g for g in used if g not in DEFAULT_GENRES)
        return Response({'results': cached('catalog', 'genres', 300, build)})


class BookEditCreate(APIView):
    def post(self, request, pk):
        book = get_object_or_404(Book, pk=pk, status=Book.Status.APPROVED)
        s = BookEditSerializer(data=request.data, context={'book': book, 'request': request})
        s.is_valid(raise_exception=True)
        d = s.validated_data
        if all(getattr(book, f) == d.get(f, '') for f in EDIT_FIELDS):
            raise Bad('Вы не изменили ни одного поля.')
        edit, _ = BookEdit.objects.update_or_create(  # у пользователя не более одной ожидающей правки на книгу
            book=book, proposed_by=request.user, status=BookEdit.Status.PENDING,
            defaults={f: d.get(f, '') for f in EDIT_FIELDS})
        return Response(BookEditSerializer(edit, context={'request': request}).data, status=201)


class Submissions(APIView):
    def get(self, request):
        ctx = {'request': request}
        books = Book.objects.select_related('created_by').filter(created_by=request.user).order_by('-id')[:50]
        edits = BookEdit.objects.select_related('book').filter(proposed_by=request.user).order_by('-created_at')[:50]
        return Response({'books': BookSerializer(books, many=True, context=ctx).data,
                         'edits': BookEditSerializer(edits, many=True, context=ctx).data})


class ModerationBooks(generics.ListAPIView):
    permission_classes = [IsModerator]
    serializer_class = BookSerializer
    queryset = Book.objects.select_related('created_by').filter(status=Book.Status.PENDING).order_by('id')


class ModerationBookAction(APIView):
    permission_classes = [IsModerator]

    def post(self, request, pk, approve):
        book = get_object_or_404(Book, pk=pk)
        if book.status != Book.Status.PENDING:
            raise Conflict('Эта книга уже обработана.')
        if approve:
            book.status, book.reject_reason = Book.Status.APPROVED, ''
        else:
            book.status = Book.Status.REJECTED
            book.reject_reason = str(request.data.get('reason') or '').strip()[:300]
        try:
            with transaction.atomic():
                book.save(update_fields=['status', 'reject_reason'])
        except IntegrityError:
            raise Conflict('Такая книга уже есть в справочнике.')
        if book.created_by_id:
            if approve:
                notify(book.created_by, 'book_approved', f'Книга «{book.title}» опубликована', 'Модератор одобрил вашу книгу — она в каталоге.', f'#/book/{book.id}')
            else:
                notify(book.created_by, 'book_rejected', f'Книга «{book.title}» отклонена', book.reject_reason or 'Причина не указана.', '#/submit')
        return Response(BookSerializer(book, context={'request': request}).data)


class ModerationEdits(generics.ListAPIView):
    permission_classes = [IsModerator]
    serializer_class = BookEditSerializer
    queryset = BookEdit.objects.select_related('book', 'proposed_by').filter(status=BookEdit.Status.PENDING)


class ModerationEditAction(APIView):
    permission_classes = [IsModerator]

    def post(self, request, pk, approve):
        with transaction.atomic():
            edit = get_object_or_404(BookEdit.objects.select_for_update().select_related('book'), pk=pk)
            if edit.status != BookEdit.Status.PENDING:
                raise Conflict('Эта правка уже обработана.')
            if approve:
                book = edit.book
                for f in EDIT_FIELDS:
                    setattr(book, f, getattr(edit, f))
                try:
                    with transaction.atomic():
                        book.save()
                except IntegrityError:
                    raise Conflict('Книга с таким названием и автором уже есть в справочнике.')
                edit.status = BookEdit.Status.APPROVED
            else:
                edit.status = BookEdit.Status.REJECTED
                edit.reject_reason = str(request.data.get('reason') or '').strip()[:300]
            edit.save(update_fields=['status', 'reject_reason'])
        if edit.proposed_by_id:
            if approve:
                notify(edit.proposed_by, 'edit_approved', f'Правка «{edit.book.title}» применена', 'Модератор одобрил вашу правку.', f'#/book/{edit.book_id}')
            else:
                notify(edit.proposed_by, 'edit_rejected', f'Правка «{edit.book.title}» отклонена', edit.reject_reason or 'Причина не указана.', '#/submit')
        return Response(BookEditSerializer(edit, context={'request': request}).data)
