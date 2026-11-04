from datetime import timedelta

from django.utils import timezone

from common.testing import BaseAPITest
from catalog.models import Book
from notifications.models import Notification

from .models import Meeting


class MeetingTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.a, self.b, self.c, self.mod = self.mk('a'), self.mk('b'), self.mk('c'), self.mk('mod', role='moderator')
        self.book = Book.objects.create(title='Оно', author='Стивен Кинг', genre='Ужасы')
        self.soon = (timezone.now() + timedelta(days=2)).isoformat()

    def test_meetings_rules(self):
        base = dict(title='Обсуждение', book_id=self.book.id, place='Библиотека', capacity=2)
        self.assertEqual(self.as_(self.a, '/api/meetings/', starts_at='2000-01-01T10:00:00Z', **base).status_code, 400)
        r = self.as_(self.a, '/api/meetings/', starts_at=self.soon, **base)
        self.assertEqual(r.status_code, 201)
        mid = r.data['id']
        self.assertTrue(r.data['is_joined'] and r.data['is_organizer'])
        self.assertEqual(self.as_(self.b, f'/api/meetings/{mid}/join/').data['participants_count'], 2)
        self.assertEqual(self.as_(self.c, f'/api/meetings/{mid}/join/').status_code, 409)  # мест нет
        self.assertEqual(self.as_(self.b, f'/api/meetings/{mid}/join/').status_code, 409)  # уже участвует
        self.assertEqual(self.as_(self.a, f'/api/meetings/{mid}/leave/').status_code, 409)  # организатор
        self.assertEqual(self.as_(self.a, f'/api/meetings/{mid}/', 'patch', capacity=1).status_code, 400)
        self.assertEqual(self.as_(self.b, f'/api/meetings/{mid}/leave/').status_code, 200)
        self.assertEqual(self.as_(self.c, f'/api/meetings/{mid}/join/').status_code, 200)
        self.assertEqual(self.as_(self.b, f'/api/meetings/{mid}/cancel/').status_code, 403)
        self.assertEqual(self.as_(self.mod, f'/api/meetings/{mid}/cancel/').status_code, 200)
        self.assertEqual(self.as_(self.b, f'/api/meetings/{mid}/join/').status_code, 409)  # отменена
        self.assertEqual(self.as_(self.b, '/api/meetings/', 'get').data['count'], 0)
        past = Meeting.objects.create(title='Было', organizer=self.a, place='X', starts_at=timezone.now() - timedelta(days=1))
        self.assertEqual(self.as_(self.b, f'/api/meetings/{past.id}/join/').status_code, 409)  # прошла
        self.assertEqual(self.as_(self.b, '/api/meetings/?when=past', 'get').data['count'], 1)

    def test_cancel_notifies_participants_except_the_actor(self):
        mid = self.as_(self.a, '/api/meetings/', title='Клуб', place='X', starts_at=self.soon).data['id']
        self.as_(self.b, f'/api/meetings/{mid}/join/')
        self.as_(self.a, f'/api/meetings/{mid}/cancel/')
        self.assertTrue(Notification.objects.filter(user=self.b, kind='meeting_cancelled').exists())
        self.assertFalse(Notification.objects.filter(user=self.a, kind='meeting_cancelled').exists())

    def test_only_approved_books_can_be_attached(self):
        pend = Book.objects.create(title='Черновик', author='А', genre='Роман', status='pending')
        r = self.as_(self.a, '/api/meetings/', title='Клуб', place='X', starts_at=self.soon, book_id=pend.id)
        self.assertEqual(r.status_code, 400)
