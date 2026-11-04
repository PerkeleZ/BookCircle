from django.utils import timezone
from rest_framework import serializers

from catalog.models import Book
from catalog.validators import approved_book
from common.validators import validate_phone_number

from .models import Copy, Loan


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
