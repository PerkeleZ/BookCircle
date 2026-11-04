from datetime import timedelta

from django.utils import timezone

from common.testing import BaseAPITest
from django.core import mail

from catalog.models import Book
from exchange.models import Copy

from .models import Notification
from .services import notify
from .tasks import deliver_email


class NotificationTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.u = self.mk('u')

    def test_list_unread_count_and_mark_read(self):
        a = notify(self.u, 'x', 'Первое', email=False)
        notify(self.u, 'x', 'Второе', email=False)
        self.assertEqual(self.as_(self.u, '/api/notifications/unread-count/', 'get').data['count'], 2)
        self.assertEqual([n['title'] for n in self.as_(self.u, '/api/notifications/', 'get').data['results']], ['Второе', 'Первое'])
        self.assertEqual(self.as_(self.u, '/api/notifications/read/', ids=[a.id]).data['updated'], 1)
        self.assertEqual(self.as_(self.u, '/api/notifications/unread-count/', 'get').data['count'], 1)
        self.assertEqual(self.as_(self.u, '/api/notifications/read/', all=True).data['updated'], 1)
        self.assertEqual(self.as_(self.mk('other'), '/api/notifications/', 'get').data['count'], 0)  # чужие не видны

    def test_email_is_sent_once_after_commit_and_respects_opt_out(self):
        with self.captureOnCommitCallbacks(execute=True):
            n = notify(self.u, 'loan_request', 'Новый запрос', 'Тело письма', '#/loans?box=incoming')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('#/loans?box=incoming', mail.outbox[0].body)
        n.refresh_from_db()
        self.assertIsNotNone(n.emailed_at)
        deliver_email(n.id)  # повторный запуск задачи не дублирует письмо
        self.assertEqual(len(mail.outbox), 1)
        self.u.notify_email = False
        self.u.save()
        with self.captureOnCommitCallbacks(execute=True):
            notify(self.u, 'x', 'Без письма')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(Notification.objects.filter(user=self.u).count(), 2)  # на сайте уведомление всё равно есть

    def test_loan_request_sends_email_to_the_owner(self):
        owner, borrower = self.mk('owner'), self.mk('borrower')
        book = Book.objects.create(title='Книга', author='А', genre='Роман')
        copy = Copy.objects.create(book=book, owner=owner, pickup_place='A')
        due = (timezone.localdate() + timedelta(days=5)).isoformat()
        with self.captureOnCommitCallbacks(execute=True):
            self.as_(borrower, f'/api/copies/{copy.id}/loans/', requested_return_date=due, phone='+996 555 123 456')
        self.assertEqual([m.to for m in mail.outbox], [['owner@example.com']])
        self.assertIn('Книга', mail.outbox[0].subject)
