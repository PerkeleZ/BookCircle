from datetime import timedelta

from django.utils import timezone

from common.testing import BaseAPITest
from catalog.models import Book
from exchange.models import Copy, Loan
from meetings.models import Meeting
from reading.models import ReadingEntry
from reviews.models import Review


class BookLifecycleTests(BaseAPITest):
    """Сквозные сценарии между приложениями (связь только через сигналы и публичные API)."""

    def setUp(self):
        super().setUp()
        self.u, self.v, self.mod = self.mk('u'), self.mk('v'), self.mk('mod', role='moderator')
        self.admin = self.mk('boss', role='admin')
        self.book = Book.objects.create(title='Старая', author='Автор', genre='Роман')
        self.url = f'/api/books/{self.book.id}/'

    def test_admin_deletes_book_with_its_data_but_not_during_active_loan(self):
        copy = Copy.objects.create(book=self.book, owner=self.u, pickup_place='A')
        loan = Loan.objects.create(copy=copy, borrower=self.v, status='accepted', borrower_phone='+996 555 000 111',
                                   requested_return_date=timezone.localdate() + timedelta(days=5))
        Review.objects.create(user=self.v, book=self.book, score=4)
        ReadingEntry.objects.create(user=self.v, book=self.book, status='reading')
        meeting = Meeting.objects.create(title='Клуб', organizer=self.u, place='X', book=self.book, starts_at=timezone.now() + timedelta(days=3))
        self.assertEqual(self.as_(self.mod, self.url, 'delete').status_code, 403)
        self.assertEqual(self.as_(self.u, self.url, 'delete').status_code, 403)
        self.assertEqual(self.as_(self.admin, self.url, 'delete').status_code, 409)  # есть активная передача
        loan.status = 'returned'
        loan.save()
        self.assertEqual(self.as_(self.admin, self.url, 'delete').status_code, 204)
        self.assertFalse(Book.objects.filter(pk=self.book.id).exists() or Copy.objects.exists() or Loan.objects.exists()
                         or Review.objects.exists() or ReadingEntry.objects.exists())
        meeting.refresh_from_db()
        self.assertIsNone(meeting.book_id)  # встреча осталась без привязки к книге
        own = self.as_(self.u, '/api/books/', title='Моя', author='А', genre='Роман').data['id']
        self.assertEqual(self.as_(self.u, f'/api/books/{own}/', 'delete').status_code, 204)  # свою неодобренную можно

    def test_hidden_book_leaves_shelves_and_cannot_be_requested(self):
        copy = Copy.objects.create(book=self.book, owner=self.u, pickup_place='A')
        self.as_(self.mod, self.url + 'hide/')
        self.assertEqual(self.as_(self.v, '/api/copies/', 'get').data['count'], 0)
        r = self.as_(self.v, f'/api/copies/{copy.id}/loans/', requested_return_date=(timezone.localdate() + timedelta(days=5)).isoformat(), phone='+996 555 123 456')
        self.assertEqual(r.status_code, 409)

    def test_only_approved_books_can_be_put_on_a_shelf(self):
        pend = Book.objects.create(title='Черновик', author='А', genre='Роман', status='pending')
        body = dict(book_id=pend.id, condition='good', pickup_place='A')
        self.assertEqual(self.as_(self.u, '/api/copies/', **body).status_code, 400)
        self.assertEqual(self.as_(self.u, '/api/copies/', book_id=self.book.id, condition='good', pickup_place='A').status_code, 201)
