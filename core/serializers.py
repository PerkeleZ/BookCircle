import re
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers
from decimal import Decimal

from .models import (Book, BookEdit, Copy, Loan, Meeting, MeetingParticipant, ReadingEntry, Review, User)

EDIT_FIELDS = ('title', 'author', 'genre', 'description', 'cover')


def validate_phone_number(v):
    v = (v or '').strip()
    digits = re.sub(r'\D', '', v)
    if not re.match(r'^\+?[\d\s\-()]{9,20}$', v) or not 9 <= len(digits) <= 15:
        raise serializers.ValidationError('Укажите номер телефона, например +996 555 123 456.')
    return v


def approved_book(book):
    if book is not None and book.status != Book.Status.APPROVED:
        raise serializers.ValidationError('Эта книга ещё не одобрена модератором.')
    return book


class UserSerializer(serializers.ModelSerializer):
    has_password = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'bio', 'phone', 'role', 'google_email', 'has_password']
        read_only_fields = ['id', 'username', 'role', 'google_email']  # роль назначает только администратор

    def get_has_password(self, o):
        return o.has_usable_password()

    def validate_email(self, v):
        if v and User.objects.filter(email__iexact=v).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError('Пользователь с таким email уже зарегистрирован.')
        return v

    def validate_phone(self, v):
        return validate_phone_number(v) if v.strip() else ''


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        extra_kwargs = {'email': {'required': True, 'allow_blank': False}}

    def validate_email(self, v):
        if User.objects.filter(email__iexact=v).exists():
            raise serializers.ValidationError('Пользователь с таким email уже зарегистрирован.')
        return v

    def validate_password(self, v):
        validate_password(v)
        return v

    def create(self, d):
        return User.objects.create_user(**d)


class CopySerializer(serializers.ModelSerializer):
    book_id = serializers.PrimaryKeyRelatedField(source='book', queryset=Book.objects.all())
    book_title = serializers.CharField(source='book.title', read_only=True)
    owner = serializers.CharField(source='owner.username', read_only=True)
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = Copy
        fields = ['id', 'book_id', 'book_title', 'owner', 'condition', 'pickup_place', 'is_active', 'is_available']

    def get_is_available(self, o):
        busy = o.busy if hasattr(o, 'busy') else o.loans.filter(status__in=Loan.ACTIVE).exists()
        return o.is_active and not busy

    def validate_book_id(self, v):
        return approved_book(v)

    def update(self, inst, vd):
        vd.pop('book', None)
        return super().update(inst, vd)


class BookSerializer(serializers.ModelSerializer):
    avg_rating = serializers.SerializerMethodField()
    available_copies = serializers.SerializerMethodField()
    read_this_month = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = ['id', 'title', 'author', 'genre', 'description', 'cover', 'status', 'reject_reason',
                  'created_by', 'is_mine', 'avg_rating', 'available_copies', 'read_this_month']
        read_only_fields = ['status', 'reject_reason']

    def validate(self, attrs):
        title = attrs.get('title', self.instance.title if self.instance else '')
        author = attrs.get('author', self.instance.author if self.instance else '')
        dup = Book.objects.filter(search_text=f'{title} {author}'.lower()).exclude(status=Book.Status.REJECTED)
        if self.instance:
            dup = dup.exclude(pk=self.instance.pk)
        if dup.exists():
            raise serializers.ValidationError({'title': ['Такая книга уже есть в справочнике или ожидает модерации.']})
        return attrs

    def get_avg_rating(self, o):
        v = getattr(o, 'avg_rating', None)
        return float(round(v, 2)) if v is not None else None

    def get_available_copies(self, o):
        return getattr(o, 'total', 0) - getattr(o, 'busy', 0)

    def get_read_this_month(self, o):
        return getattr(o, 'read_month', 0)

    def get_created_by(self, o):
        return o.created_by.username if o.created_by_id else None

    def get_is_mine(self, o):
        r = self.context.get('request')
        return bool(r and r.user.is_authenticated and o.created_by_id == r.user.id)


class BookDetailSerializer(BookSerializer):
    copies = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    my_review = serializers.SerializerMethodField()
    my_reading = serializers.SerializerMethodField()

    class Meta(BookSerializer.Meta):
        fields = BookSerializer.Meta.fields + ['copies', 'reviews', 'my_review', 'my_reading']

    def _user(self):
        u = self.context['request'].user
        return u if u.is_authenticated else None

    def get_copies(self, o):
        qs = Copy.objects.with_busy().select_related('book', 'owner').filter(book=o, is_active=True)
        return CopySerializer(qs, many=True).data

    def get_reviews(self, o):
        u = self._user()
        qs = o.reviews.filter(is_hidden=False).select_related('user').order_by('-updated_at')
        return [{'id': r.id, 'user': r.user.username, 'score': float(r.score), 'text': r.text,
                 'is_mine': bool(u and r.user_id == u.id)} for r in qs]

    def get_my_review(self, o):
        u = self._user()
        r = o.reviews.filter(user=u).first() if u else None
        return {'score': float(r.score), 'text': r.text, 'is_hidden': r.is_hidden} if r else None

    def get_my_reading(self, o):
        u = self._user()
        e = o.entries.filter(user=u).first() if u else None
        return e.status if e else None


class LoanSerializer(serializers.ModelSerializer):
    book_id = serializers.IntegerField(source='copy.book_id', read_only=True)
    book_title = serializers.CharField(source='copy.book.title', read_only=True)
    owner = serializers.CharField(source='copy.owner.username', read_only=True)
    borrower = serializers.CharField(source='borrower.username', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    owner_phone = serializers.SerializerMethodField()
    days_left = serializers.SerializerMethodField()
    is_due_soon = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = ['id', 'copy_id', 'book_id', 'book_title', 'owner', 'borrower', 'borrower_phone', 'owner_phone',
                  'requested_return_date', 'status', 'handed_at', 'returned_at', 'is_overdue', 'days_left', 'is_due_soon']

    def get_owner_phone(self, o):  # телефон владельца открывается получателю после принятия запроса
        return o.copy.owner.phone if o.status in Loan.ACTIVE else ''

    def get_days_left(self, o):  # отрицательное число — просрочка
        if o.status != Loan.Status.HANDED_OVER:
            return None
        return (o.requested_return_date - timezone.localdate()).days

    def get_is_due_soon(self, o):
        d = self.get_days_left(o)
        return d is not None and 0 <= d <= 2


class LoanCreateSerializer(serializers.Serializer):
    requested_return_date = serializers.DateField()
    phone = serializers.CharField(max_length=20)

    def validate_requested_return_date(self, v):
        if v <= timezone.localdate():
            raise serializers.ValidationError('Дата возврата должна быть в будущем.')
        return v

    def validate_phone(self, v):
        return validate_phone_number(v)


class ReadingSerializer(serializers.ModelSerializer):
    book_id = serializers.IntegerField(read_only=True)
    book_title = serializers.CharField(source='book.title', read_only=True)

    class Meta:
        model = ReadingEntry
        fields = ['book_id', 'book_title', 'status', 'finished_at']


class ReadingInputSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ReadingEntry.Status.choices)
    finished_at = serializers.DateField(required=False, allow_null=True)

    def validate_finished_at(self, v):
        if v and v > timezone.localdate():
            raise serializers.ValidationError('Дата завершения не может быть в будущем.')
        return v


class ReviewInputSerializer(serializers.Serializer):
    score = serializers.DecimalField(max_digits=2, decimal_places=1, min_value=Decimal('0.5'), max_value=Decimal('5.0'))
    text = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate_score(self, v):
        if (v * 2) % 1 != 0:
            raise serializers.ValidationError('Оценка ставится с шагом 0,5 (например, 3,5).')
        return v


class ModerationReviewSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source='user.username', read_only=True)
    book_id = serializers.IntegerField(read_only=True)
    book_title = serializers.CharField(source='book.title', read_only=True)
    score = serializers.FloatField(read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'user', 'book_id', 'book_title', 'score', 'text', 'is_hidden']
        read_only_fields = ['score', 'text']


class MeetingSerializer(serializers.ModelSerializer):
    book_id = serializers.PrimaryKeyRelatedField(source='book', queryset=Book.objects.all(), allow_null=True, required=False)
    book_title = serializers.SerializerMethodField()
    organizer = serializers.CharField(source='organizer.username', read_only=True)
    participants_count = serializers.SerializerMethodField()
    is_joined = serializers.SerializerMethodField()
    is_organizer = serializers.SerializerMethodField()
    is_full = serializers.SerializerMethodField()
    is_past = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = ['id', 'title', 'description', 'book_id', 'book_title', 'organizer', 'starts_at', 'place',
                  'capacity', 'is_cancelled', 'participants_count', 'is_joined', 'is_organizer', 'is_full', 'is_past']
        read_only_fields = ['is_cancelled']
        extra_kwargs = {'capacity': {'min_value': 1, 'required': False, 'allow_null': True},
                        'description': {'required': False}}

    def _user(self):
        r = self.context.get('request')
        return r.user if r and r.user.is_authenticated else None

    def validate_book_id(self, v):
        return approved_book(v)

    def validate_starts_at(self, v):
        if (self.instance is None or v != self.instance.starts_at) and v <= timezone.now():
            raise serializers.ValidationError('Время встречи должно быть в будущем.')
        return v

    def get_book_title(self, o):
        return o.book.title if o.book_id else None

    def get_participants_count(self, o):
        return o.n_participants if hasattr(o, 'n_participants') else o.participants.count()

    def get_is_joined(self, o):
        if hasattr(o, 'joined'):
            return o.joined
        u = self._user()
        return bool(u and o.participants.filter(user=u).exists())

    def get_is_organizer(self, o):
        u = self._user()
        return bool(u and o.organizer_id == u.id)

    def get_is_full(self, o):
        return o.capacity is not None and self.get_participants_count(o) >= o.capacity

    def get_is_past(self, o):
        return o.starts_at < timezone.now()


class MeetingDetailSerializer(MeetingSerializer):
    participants = serializers.SerializerMethodField()

    class Meta(MeetingSerializer.Meta):
        fields = MeetingSerializer.Meta.fields + ['participants']

    def get_participants(self, o):
        return [p.user.username for p in o.participants.select_related('user').order_by('joined_at')]


class GoalInputSerializer(serializers.Serializer):
    period = serializers.ChoiceField(choices=['year', 'month'])
    target = serializers.IntegerField(min_value=1, max_value=365)


class BookEditSerializer(serializers.ModelSerializer):
    book_id = serializers.IntegerField(read_only=True)
    book_title = serializers.CharField(source='book.title', read_only=True)
    proposed_by = serializers.CharField(source='proposed_by.username', read_only=True, default=None)
    current = serializers.SerializerMethodField()

    class Meta:
        model = BookEdit
        fields = ['id', 'book_id', 'book_title', 'title', 'author', 'genre', 'description', 'cover', 'status',
                  'reject_reason', 'proposed_by', 'created_at', 'current']
        read_only_fields = ['status', 'reject_reason', 'created_at']

    def get_current(self, o):
        return {f: getattr(o.book, f) for f in EDIT_FIELDS}

    def validate(self, attrs):
        book = self.context.get('book')
        if book is not None:
            key = f"{attrs['title']} {attrs['author']}".lower()
            if Book.objects.filter(search_text=key).exclude(pk=book.pk).exclude(status=Book.Status.REJECTED).exists():
                raise serializers.ValidationError({'title': ['Книга с таким названием и автором уже есть в справочнике.']})
        return attrs
