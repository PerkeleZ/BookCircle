from django.utils import timezone
from rest_framework import serializers

from catalog.models import Book
from catalog.validators import approved_book

from .models import Meeting


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
