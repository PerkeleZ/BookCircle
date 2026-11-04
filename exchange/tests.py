from datetime import timedelta

from django.utils import timezone

from common.testing import BaseAPITest
from unittest.mock import patch

from django.db import IntegrityError, transaction

from catalog.models import Book
from notifications.models import Notification

from . import services
from .models import Copy, Loan

PHONE = '+996 555 123 456'


class ExchangeBase(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.o1, self.o2, self.b1, self.b2 = self.mk('o1'), self.mk('o2'), self.mk('b1'), self.mk('b2')
        self.book = Book.objects.create(title='Тест', author='Автор', genre='Роман')
        self.c1 = Copy.objects.create(book=self.book, owner=self.o1, pickup_place='A')
        self.c2 = Copy.objects.create(book=self.book, owner=self.o2, pickup_place='B')
        self.due = (timezone.localdate() + timedelta(days=7)).isoformat()

    def req(self, user, copy, date=None, phone=PHONE):
        return self.as_(user, f'/api/copies/{copy.id}/loans/', requested_return_date=date or self.due, phone=phone)

    def act(self, user, loan_id, action):
        return self.as_(user, f'/api/loans/{loan_id}/{action}/')

    def available(self):
        return self.anon(f'/api/books/{self.book.id}/').data['available_copies']


class LoanFlowTests(ExchangeBase):
    def test_two_copies_book_independently(self):
        l1, l2 = self.req(self.b1, self.c1).data['id'], self.req(self.b2, self.c2).data['id']
        self.assertEqual(self.act(self.o1, l1, 'accept').status_code, 200)
        self.assertEqual(self.act(self.o2, l2, 'accept').status_code, 200)
        self.assertEqual(self.available(), 0)

    def test_full_cycle_restores_availability_and_notifies_borrower(self):
        self.assertEqual(self.available(), 2)
        lid = self.req(self.b1, self.c1).data['id']
        self.assertTrue(Notification.objects.filter(user=self.o1, kind='loan_request').exists())  # владелец уведомлён о запросе
        self.act(self.o1, lid, 'accept')
        self.assertEqual(self.available(), 1)
        self.assertEqual(self.act(self.o1, lid, 'hand-over').data['status'], 'handed_over')
        self.assertEqual(self.act(self.o1, lid, 'return').data['status'], 'returned')
        self.assertEqual(self.available(), 2)
        kinds = set(Notification.objects.filter(user=self.b1).values_list('kind', flat=True))
        self.assertEqual(kinds, {'loan_accepted', 'loan_handed_over', 'loan_returned'})

    def test_cannot_accept_two_borrowers(self):
        l1, l2 = self.req(self.b1, self.c1).data['id'], self.req(self.b2, self.c1).data['id']
        self.assertEqual(self.act(self.o1, l1, 'accept').status_code, 200)
        self.assertEqual(Loan.objects.get(pk=l2).status, 'rejected')  # второй отклонён автоматически
        self.assertEqual(self.act(self.o1, l2, 'accept').status_code, 409)
        with self.assertRaises(IntegrityError), transaction.atomic():  # и на уровне БД
            Loan.objects.create(copy=self.c1, borrower=self.b2, status='accepted', requested_return_date=self.due)

    def test_permissions_validation_and_transitions(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/loans/').status_code, 401)
        self.assertEqual(self.req(self.o1, self.c1).status_code, 400)  # своя книга
        self.assertEqual(self.req(self.b1, self.c1, '2000-01-01').status_code, 400)  # прошлая дата
        lid = self.req(self.b1, self.c1).data['id']
        self.assertEqual(self.act(self.b2, lid, 'accept').status_code, 403)  # не владелец
        self.assertEqual(self.act(self.o1, lid, 'return').status_code, 409)  # недопустимый переход
        self.act(self.o1, lid, 'accept')
        r = self.as_(self.o1, f'/api/copies/{self.c1.id}/', 'patch', is_active=False)
        self.assertEqual(r.status_code, 409)  # занятый экземпляр нельзя скрыть

    def test_cancel_notifies_both_sides_and_unknown_action_is_404(self):
        lid = self.req(self.b1, self.c1).data['id']
        self.act(self.b1, lid, 'cancel')
        self.assertTrue(Notification.objects.filter(user=self.o1, kind='loan_cancelled').exists())
        self.assertEqual(self.act(self.o1, lid, 'explode').status_code, 404)

    def test_book_copies_endpoint_is_public(self):
        r = self.anon(f'/api/books/{self.book.id}/copies/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual([c['is_available'] for c in r.data['results']], [True, True])
        hidden = Book.objects.create(title='Скрытая', author='А', genre='Роман', status='hidden')
        self.assertEqual(self.anon(f'/api/books/{hidden.id}/copies/').status_code, 404)


class RentalTests(ExchangeBase):
    def test_phone_required_and_rental_alerts(self):
        url = f'/api/copies/{self.c1.id}/loans/'
        self.assertIn('phone', self.as_(self.b1, url, requested_return_date=self.due).data)  # без телефона
        self.assertIn('phone', self.as_(self.b1, url, requested_return_date=self.due, phone='abc').data)
        r = self.req(self.b1, self.c1)
        self.assertEqual(r.status_code, 201)
        lid = r.data['id']
        owner_view = self.as_(self.o1, '/api/loans/?box=incoming', 'get').data['results'][0]
        self.assertEqual((owner_view['borrower_phone'], owner_view['owner_phone']), (PHONE, ''))
        self.o1.phone = '+996 700 111 222'
        self.o1.save()
        self.act(self.o1, lid, 'accept')
        self.act(self.o1, lid, 'hand-over')
        mine = self.as_(self.b1, '/api/loans/?box=outgoing', 'get').data['results'][0]
        self.assertEqual((mine['owner_phone'], mine['days_left']), ('+996 700 111 222', 7))
        self.assertEqual(self.as_(self.b1, '/api/alerts/', 'get').data['count'], 0)  # срок ещё далеко
        Loan.objects.filter(pk=lid).update(requested_return_date=timezone.localdate() - timedelta(days=3))
        for who, role in ((self.b1, 'borrower'), (self.o1, 'owner')):  # просрочка видна обеим сторонам
            a = self.as_(who, '/api/alerts/', 'get').data
            self.assertEqual((a['overdue'], a['results'][0]['role'], a['results'][0]['days_left']), (1, role, -3))
        self.assertEqual(self.as_(self.mk('stranger'), '/api/alerts/', 'get').data['count'], 0)
        self.assertEqual(len(self.as_(self.o1, '/api/loans/?box=active', 'get').data['results']), 1)

    def test_overdue_reminders_are_sent_once_a_day(self):
        lid = self.req(self.b1, self.c1).data['id']
        self.act(self.o1, lid, 'accept')
        self.act(self.o1, lid, 'hand-over')
        Loan.objects.filter(pk=lid).update(requested_return_date=timezone.localdate() - timedelta(days=2))
        self.assertEqual(services.remind_overdue(email=False), 1)
        self.assertEqual(services.remind_overdue(email=False), 0)  # повторно в тот же день — нет
        self.assertEqual(Notification.objects.filter(kind='loan_overdue').count(), 2)  # получателю и владельцу
        self.assertEqual(services.remind_overdue(today=timezone.localdate() + timedelta(days=1), email=False), 1)  # на следующий день — снова

    def test_celery_task_wraps_the_service(self):
        from .tasks import remind_overdue
        with patch('exchange.services.remind_overdue', return_value=3) as m:
            self.assertEqual(remind_overdue(), 3)
        m.assert_called_once()
