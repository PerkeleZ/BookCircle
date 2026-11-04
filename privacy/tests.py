from datetime import timedelta

from django.utils import timezone

from common.testing import BaseAPITest
from rest_framework.authtoken.models import Token

from accounts.models import User
from catalog.models import Book
from exchange.models import Copy, Loan
from notifications.services import notify
from reviews.models import Review


class PrivacyTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.u, self.v = self.mk('u', phone='+996 555 000 111'), self.mk('v')
        self.book = Book.objects.create(title='Книга', author='А', genre='Роман')
        self.copy = Copy.objects.create(book=self.book, owner=self.u, pickup_place='A')
        self.due = timezone.localdate() + timedelta(days=5)
        self.loan = Loan.objects.create(copy=self.copy, borrower=self.v, status='accepted', requested_return_date=self.due, borrower_phone='+996 555 222 333')

    def test_export_contains_own_data_and_downloads_as_file(self):
        self.as_(self.u, f'/api/books/{self.book.id}/review/', 'put', score=4.5, text='ok')
        notify(self.u, 'x', 'Привет', email=False)
        r = self.as_(self.u, '/api/privacy/export/', 'get')
        self.assertEqual(r.status_code, 200)
        self.assertIn('attachment', r['Content-Disposition'])
        d = r.data
        self.assertEqual(d['profile']['phone'], '+996 555 000 111')
        self.assertEqual(d['reviews'][0]['score'], 4.5)
        self.assertEqual(d['loans_as_owner'][0]['borrower'], 'v')
        self.assertNotIn('phone_given', d['loans_as_owner'][0])  # телефон получателя не попадает в выгрузку владельца
        self.assertEqual(d['notifications'][0]['title'], 'Привет')

    def test_erase_requires_confirmation_and_is_blocked_by_active_loans(self):
        self.assertIn('password', self.as_(self.u, '/api/privacy/erase/', confirm='u', password='bad').data)
        self.assertIn('confirm', self.as_(self.u, '/api/privacy/erase/', confirm='wrong', password='x12345678').data)
        r = self.as_(self.u, '/api/privacy/erase/', confirm='u', password='x12345678')
        self.assertEqual(r.status_code, 409)  # есть принятая передача
        self.assertTrue(User.objects.get(pk=self.u.pk).is_active)

    def test_erase_anonymises_and_keeps_other_peoples_history(self):
        self.loan.status = 'returned'
        self.loan.save()
        self.as_(self.u, f'/api/books/{self.book.id}/review/', 'put', score=5, text='мой отзыв')
        Token.objects.get_or_create(user=self.u)
        r = self.as_(self.u, '/api/privacy/erase/', confirm='u', password='x12345678')
        self.assertEqual(r.status_code, 204)
        u = User.objects.get(pk=self.u.pk)
        self.assertEqual((u.username, u.email, u.phone, u.is_active), (f'deleted-{u.id}', '', '', False))
        self.assertFalse(u.has_usable_password())
        self.assertFalse(Review.objects.filter(user=u).exists() or Token.objects.filter(user=u).exists())
        self.assertFalse(self.client.post('/api/auth/login/', {'username': 'u', 'password': 'x12345678'}, format='json').status_code == 200)
        self.assertTrue(Loan.objects.filter(pk=self.loan.pk).exists())  # история обмена осталась у второй стороны
        self.assertEqual(self.as_(self.v, '/api/loans/?box=outgoing', 'get').data['results'][0]['owner'], f'deleted-{u.id}')
        self.assertFalse(Copy.objects.get(pk=self.copy.pk).is_active)  # экземпляр с историей скрыт, а не удалён
