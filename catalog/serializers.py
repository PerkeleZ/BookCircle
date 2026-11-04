from rest_framework import serializers

from .models import Book, BookEdit


EDIT_FIELDS = ('title', 'author', 'genre', 'description', 'cover')


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
