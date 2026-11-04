from rest_framework import serializers

from .models import Book


def approved_book(book):
    if book is not None and book.status != Book.Status.APPROVED:
        raise serializers.ValidationError('Эта книга ещё не одобрена модератором.')
    return book
