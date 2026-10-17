import logging
import re
import secrets
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.utils.crypto import constant_time_compare, salted_hmac
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import SAFE_METHODS, AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import google_auth
from .models import Book, Copy, Loan, PasswordResetCode, ReadingEntry, Review, User
from .serializers import (BookDetailSerializer, BookSerializer, CopySerializer, LoanCreateSerializer,
                          LoanSerializer, ModerationReviewSerializer, ReadingInputSerializer,
                          ReadingSerializer, RegisterSerializer, ReviewInputSerializer, UserSerializer)

from collections import Counter

from django.db.models import Exists, OuterRef

from datetime import timedelta

from .models import DEFAULT_GENRES, BookEdit, Meeting, MeetingParticipant, ReadingGoal
from .serializers import BookEditSerializer, GoalInputSerializer, MeetingDetailSerializer, MeetingSerializer

S = Loan.Status
logger = logging.getLogger(__name__)


class Conflict(APIException):  # 409 — конфликт состояния
    status_code = 409
    default_detail = 'Конфликт состояния.'
    default_code = 'conflict'


class Bad(APIException):  # 400 с понятным сообщением
    status_code = 400
    default_code = 'bad_request'


class MailFailed(APIException):
    status_code = 503
    default_detail = 'Не удалось отправить письмо. Проверьте настройку EMAIL_BACKEND в settings.py.'


class IsModerator(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_moderator)


class IsModeratorOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or bool(request.user.is_authenticated and request.user.is_moderator)


class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.owner_id == request.user.id


# ---------- Аутентификация и профиль ----------
class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.save()
        return Response({'token': Token.objects.get_or_create(user=user)[0].key}, status=201)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        user = authenticate(username=request.data.get('username'), password=request.data.get('password'))
        if not user:
            raise Bad('Неверный логин или пароль.')
        return Response({'token': Token.objects.get_or_create(user=user)[0].key})


class LogoutView(APIView):
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=204)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


# ---------- Каталог ----------
class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.role == User.Role.ADMIN)


EDIT_FIELDS = ('title', 'author', 'genre', 'description', 'cover')


def book_qs(public=True):
    now = timezone.localdate()
    qs = Book.objects.select_related('created_by').annotate(
        avg_rating=Avg('reviews__score', filter=Q(reviews__is_hidden=False)),  # скрытые отзывы не учитываются
        total=Count('copies', filter=Q(copies__is_active=True), distinct=True),
        busy=Count('copies', filter=Q(copies__loans__status__in=Loan.ACTIVE), distinct=True),
        read_month=Count('entries', filter=Q(entries__status='done', entries__finished_at__year=now.year,
                                             entries__finished_at__month=now.month), distinct=True),
    )
    if public:  # на сайте видны только одобренные модератором книги
        qs = qs.filter(status=Book.Status.APPROVED)
    return qs.order_by('title')


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
        return BookDetailSerializer if self.request.method == 'GET' else BookSerializer

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
        if not (u.role == User.Role.ADMIN or own_draft):
            raise PermissionDenied('Удалять книги может только администратор.')
        with transaction.atomic():
            if Loan.objects.filter(copy__book=book, status__in=Loan.ACTIVE).exists():
                raise Conflict('У книги есть принятые или переданные экземпляры — дождитесь возврата.')
            Loan.objects.filter(copy__book=book).delete()  # история обменов удаляется явно, а не каскадом
            Copy.objects.filter(book=book).delete()
            Review.objects.filter(book=book).delete()
            ReadingEntry.objects.filter(book=book).delete()
            Meeting.objects.filter(book=book).update(book=None)  # встречи остаются, но без привязки к книге
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
    """Все одобренные книги без пагинации — для выпадающих списков («Моя полка», встречи)."""

    def get(self, request):
        rows = Book.objects.filter(status=Book.Status.APPROVED).order_by('title').values('id', 'title', 'author', 'genre')
        return Response({'results': list(rows)})


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
        return Response(BookEditSerializer(edit, context={'request': request}).data)


# ---------- Экземпляры ----------
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


# ---------- Передачи ----------
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
        return Response(LoanSerializer(loan).data, status=201)


# действие: (допустимые исходные статусы, новый статус, кто может)
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
        return Response(LoanSerializer(loan).data)


# ---------- Чтение и рецензии ----------
class ReadingList(APIView):
    def get(self, request):
        qs = ReadingEntry.objects.filter(user=request.user).select_related('book').order_by('status', 'book__title')
        t = timezone.localdate()
        n = qs.filter(status='done', finished_at__year=t.year, finished_at__month=t.month).count()
        return Response({'results': ReadingSerializer(qs, many=True).data, 'finished_this_month': n})


class ReadingUpdate(APIView):
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
    queryset = Review.objects.select_related('user', 'book')


# ---------- Сброс пароля (код и ссылка печатаются в терминал) ----------
RESET_TTL = timedelta(minutes=10)
RESET_MAX_ATTEMPTS = 5


def _code_hash(user, code):  # в базе хранится только HMAC-хэш кода, не сам код
    return salted_hmac('bookcircle.pwreset', f'{user.pk}:{code}').hexdigest()


class PasswordResetRequest(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        email = (request.data.get('email') or '').strip()
        if not email:
            raise ValidationError({'email': ['Укажите email.']})
        users = list(User.objects.filter(email__iexact=email, is_active=True))
        if not users and (settings.DEBUG or settings.EMAIL_BACKEND.endswith('TerminalEmailBackend')):  # только в разработке: иначе непонятно, почему «ничего не пришло»
            print(f'\n[dev] Сброс пароля: пользователь с email «{email}» не найден — письмо не создано.\n', flush=True)
            raise NotFound(f'Аккаунт с email «{email}» не найден. (Подсказка режима разработки: '
                           f'в рабочей версии ответ одинаковый для любых адресов.)')
        for u in users:
            code = f'{secrets.randbelow(10 ** 6):06d}'
            PasswordResetCode.objects.filter(user=u).delete()  # новый код отменяет предыдущий
            PasswordResetCode.objects.create(user=u, code_hash=_code_hash(u, code))
            link = f"{settings.FRONTEND_URL}/#/reset?email={quote(u.email, safe='')}&code={code}"
            try:
                send_mail('BookCircle: код для сброса пароля',
                          f'Здравствуйте, {u.username}!\n\nВаш код для сброса пароля: {code}\n\n'
                          f'Или откройте ссылку — код подставится сам:\n{link}\n\n'
                          f'Код действует 10 минут и работает один раз. Если вы не запрашивали сброс — '
                          f'просто проигнорируйте это письмо.',
                          settings.DEFAULT_FROM_EMAIL, [u.email])
            except Exception:
                logger.exception('Не удалось отправить письмо сброса пароля')
                raise MailFailed()
        msg = 'Если аккаунт с таким email существует, код отправлен.'
        if settings.EMAIL_BACKEND.endswith('TerminalEmailBackend'):
            msg = 'Код выведен в терминал, где запущен сервер (почта и Gmail не используются).'
        return Response({'detail': msg})  # в рабочей версии ответ одинаков для любых email


class PasswordResetConfirm(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        email, code, pwd = (str(request.data.get(k) or '').strip() for k in ('email', 'code', 'password'))
        user = User.objects.filter(email__iexact=email, is_active=True).first() if email else None
        wrong = False
        with transaction.atomic():
            rc = PasswordResetCode.objects.select_for_update().filter(user=user).first() if user else None
            if not rc or timezone.now() - rc.created_at > RESET_TTL or rc.attempts >= RESET_MAX_ATTEMPTS:
                raise Bad('Код недействителен или устарел. Запросите новый.')
            if not constant_time_compare(rc.code_hash, _code_hash(user, code)):
                rc.attempts += 1
                rc.save(update_fields=['attempts'])
                wrong = True
        if wrong:  # исключение — вне транзакции, чтобы счётчик попыток сохранился
            raise ValidationError({'code': ['Неверный код.']})
        try:
            validate_password(pwd, user)
        except DjangoValidationError as e:
            raise ValidationError({'password': list(e.messages)})
        user.set_password(pwd)
        user.save()
        PasswordResetCode.objects.filter(user=user).delete()  # код одноразовый
        Token.objects.filter(user=user).delete()  # выход на всех устройствах
        return Response({'detail': 'Пароль изменён. Теперь можно войти.'})


# ---------- Google ----------
class Unavailable(APIException):
    status_code = 503
    default_detail = 'Вход через Google не настроен на сервере (переменная GOOGLE_CLIENT_ID).'


def google_info(request):
    try:
        return google_auth.verify(request.data.get('credential') or '')
    except google_auth.NotConfigured:
        raise Unavailable()
    except google_auth.InvalidCredential:
        raise Bad('Не удалось проверить вход через Google. Попробуйте ещё раз.')


class PublicConfig(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({'client_id': settings.GOOGLE_CLIENT_ID})


class GoogleLogin(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        info = google_info(request)
        sub, email = info['sub'], info['email'].lower()
        user = User.objects.filter(google_sub=sub).first()
        if not user:
            # автопривязки по email нет: иначе можно угнать чужой аккаунт, зарегистрированный на чужой email
            if User.objects.filter(email__iexact=email).exists():
                raise Conflict('Аккаунт с этим email уже существует. Войдите по паролю и привяжите Google в профиле.')
            base = re.sub(r'[^\w.@+-]', '', email.split('@')[0])[:30] or 'user'
            name, n = base, 1
            while User.objects.filter(username=name).exists():
                n += 1
                name = f'{base}{n}'
            user = User(username=name, email=email, google_sub=sub, google_email=email)
            user.set_unusable_password()
            user.save()
        return Response({'token': Token.objects.get_or_create(user=user)[0].key})


class GoogleLink(APIView):
    def post(self, request):
        info = google_info(request)
        if User.objects.filter(google_sub=info['sub']).exclude(pk=request.user.pk).exists():
            raise Conflict('Этот Google-аккаунт уже привязан к другому пользователю.')
        request.user.google_sub = info['sub']
        request.user.google_email = info['email']
        request.user.save(update_fields=['google_sub', 'google_email'])
        return Response({'google_email': info['email']})


class GoogleUnlink(APIView):
    def post(self, request):
        if not request.user.has_usable_password():
            raise Conflict('Нельзя отвязать Google: у аккаунта нет пароля. Сначала задайте его через «Забыли пароль?».')
        request.user.google_sub = None
        request.user.google_email = ''
        request.user.save(update_fields=['google_sub', 'google_email'])
        return Response({'google_email': ''})


# ---------- Жанры ----------
class GenreList(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        used = Book.objects.filter(status=Book.Status.APPROVED).order_by().values_list('genre', flat=True).distinct()
        return Response({'results': DEFAULT_GENRES + sorted(g for g in used if g not in DEFAULT_GENRES)})


# ---------- Книжные встречи ----------
def meeting_qs(user):
    qs = Meeting.objects.select_related('book', 'organizer').annotate(n_participants=Count('participants', distinct=True))
    if user.is_authenticated:
        qs = qs.annotate(joined=Exists(MeetingParticipant.objects.filter(meeting=OuterRef('pk'), user=user)))
    return qs


def meeting_data(request, pk):
    return MeetingSerializer(meeting_qs(request.user).get(pk=pk), context={'request': request}).data


class MeetingList(generics.ListCreateAPIView):
    serializer_class = MeetingSerializer

    def get_queryset(self):
        p, now = self.request.query_params, timezone.now()
        qs = meeting_qs(self.request.user)
        if (b := p.get('book', '')).isdigit():
            qs = qs.filter(book_id=int(b))
        when = p.get('when', 'upcoming')
        if when == 'past':
            return qs.filter(starts_at__lt=now).order_by('-starts_at')
        if when == 'mine':
            return qs.filter(starts_at__gte=now, joined=True).order_by('starts_at')
        return qs.filter(starts_at__gte=now, is_cancelled=False).order_by('starts_at')

    def perform_create(self, s):
        with transaction.atomic():
            m = s.save(organizer=self.request.user)
            MeetingParticipant.objects.create(meeting=m, user=self.request.user)  # организатор идёт сам


class MeetingDetail(generics.RetrieveUpdateAPIView):
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        return meeting_qs(self.request.user)

    def get_serializer_class(self):
        return MeetingDetailSerializer if self.request.method == 'GET' else MeetingSerializer

    def perform_update(self, s):
        m, u = s.instance, self.request.user
        if not (m.organizer_id == u.id or u.is_moderator):
            raise PermissionDenied('Редактировать встречу может только организатор.')
        if m.is_cancelled or m.starts_at < timezone.now():
            raise Conflict('Отменённую или прошедшую встречу изменить нельзя.')
        cap = s.validated_data.get('capacity', m.capacity)
        if cap is not None and cap < m.participants.count():
            raise ValidationError({'capacity': ['Участников уже больше, чем мест.']})
        s.save()


class MeetingJoin(APIView):
    def post(self, request, pk):
        with transaction.atomic():
            m = get_object_or_404(Meeting.objects.select_for_update(), pk=pk)  # блокировка: места не «перепродаются»
            if m.is_cancelled:
                raise Conflict('Встреча отменена.')
            if m.starts_at < timezone.now():
                raise Conflict('Встреча уже прошла.')
            if m.participants.filter(user=request.user).exists():
                raise Conflict('Вы уже участвуете во встрече.')
            if m.capacity is not None and m.participants.count() >= m.capacity:
                raise Conflict('Свободных мест не осталось.')
            MeetingParticipant.objects.create(meeting=m, user=request.user)
        return Response(meeting_data(request, pk))


class MeetingLeave(APIView):
    def post(self, request, pk):
        m = get_object_or_404(Meeting, pk=pk)
        if m.organizer_id == request.user.id:
            raise Conflict('Организатор не может покинуть встречу — отмените её.')
        deleted, _ = MeetingParticipant.objects.filter(meeting=m, user=request.user).delete()
        if not deleted:
            raise Conflict('Вы не участвуете в этой встрече.')
        return Response(meeting_data(request, pk))


class MeetingCancel(APIView):
    def post(self, request, pk):
        m = get_object_or_404(Meeting, pk=pk)
        if not (m.organizer_id == request.user.id or request.user.is_moderator):
            raise PermissionDenied('Отменить встречу может только организатор или модератор.')
        if m.is_cancelled:
            raise Conflict('Встреча уже отменена.')
        m.is_cancelled = True
        m.save(update_fields=['is_cancelled'])
        return Response(meeting_data(request, pk))


# ---------- Цели чтения ----------
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


# ---------- Рекомендации по жанрам ----------
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


# ---------- Отслеживание аренды: предупреждения о сроках ----------
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
