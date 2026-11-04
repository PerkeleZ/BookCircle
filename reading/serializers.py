from django.utils import timezone
from rest_framework import serializers

from .models import ReadingEntry


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


class GoalInputSerializer(serializers.Serializer):
    period = serializers.ChoiceField(choices=['year', 'month'])
    target = serializers.IntegerField(min_value=1, max_value=365)
