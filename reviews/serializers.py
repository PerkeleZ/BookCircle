from rest_framework import serializers

from .models import Review


class ReviewInputSerializer(serializers.Serializer):
    score = serializers.DecimalField(max_digits=2, decimal_places=1, min_value=1, max_value=5)
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
