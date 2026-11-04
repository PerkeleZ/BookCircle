import re
from unittest.mock import patch

from django.core import mail
from django.test import override_settings

from common.testing import BaseAPITest

from .models import User


class AuthBase(BaseAPITest):
    def post(self, url, **data):
        return self.client.post(url, data, format='json')


class PasswordResetTests(AuthBase):
    def setUp(self):
        super().setUp()
        self.u = User.objects.create_user('ann', email='ann@example.com', password='Old-pass-12345')

    def code_from_mail(self):
        return re.search(r'код для сброса пароля: (\d{6})', mail.outbox[-1].body).group(1)

    def test_password_reset_code_flow(self):
        confirm = '/api/auth/password-reset/confirm/'
        self.assertEqual(self.post('/api/auth/password-reset/', email='ANN@example.com').status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        code = self.code_from_mail()
        self.assertIn(f'#/reset?email=ann%40example.com&code={code}', mail.outbox[0].body)  # ссылка с кодом
        wrong = '000000' if code != '000000' else '111111'
        r = self.post(confirm, email='ann@example.com', code=wrong, password='New-pass-98765')
        self.assertEqual(r.status_code, 400)
        self.assertIn('code', r.data)
        weak = self.post(confirm, email='ann@example.com', code=code, password='123')
        self.assertEqual(weak.status_code, 400)
        self.assertIn('password', weak.data)
        self.assertEqual(self.post(confirm, email='ann@example.com', code=code, password='New-pass-98765').status_code, 200)
        self.assertTrue(User.objects.get(pk=self.u.pk).check_password('New-pass-98765'))
        self.assertEqual(self.post(confirm, email='ann@example.com', code=code, password='Other-pass-5555').status_code, 400)  # одноразовый
        self.assertEqual(self.post('/api/auth/password-reset/', email='nobody@example.com').status_code, 200)
        self.assertEqual(len(mail.outbox), 1)  # на неизвестный email письмо не уходит, ответ тот же

    def test_reset_code_locked_after_five_wrong_attempts(self):
        confirm = '/api/auth/password-reset/confirm/'
        self.post('/api/auth/password-reset/', email='ann@example.com')
        code = self.code_from_mail()
        wrong = '000000' if code != '000000' else '111111'
        for _ in range(5):
            self.assertEqual(self.post(confirm, email='ann@example.com', code=wrong, password='New-pass-98765').status_code, 400)
        self.assertEqual(self.post(confirm, email='ann@example.com', code=code, password='New-pass-98765').status_code, 400)

    def test_reset_dev_hints_and_mail_failure(self):
        with override_settings(DEBUG=True):  # в разработке неизвестный email — явная подсказка, а не молчание
            self.assertEqual(self.post('/api/auth/password-reset/', email='nobody@gmail.com').status_code, 404)
        with patch('accounts.views.send_mail', side_effect=OSError('smtp down')):
            self.assertEqual(self.post('/api/auth/password-reset/', email='ann@example.com').status_code, 503)


class GoogleTests(AuthBase):
    def setUp(self):
        super().setUp()
        self.u = User.objects.create_user('ann', email='ann@example.com', password='Old-pass-12345')

    @patch('accounts.google_auth.verify')
    def test_google_login_creates_reuses_and_never_autolinks(self, v):
        v.return_value = {'sub': 'g-1', 'email': 'new@example.com'}
        r1, r2 = self.post('/api/auth/google/', credential='x'), self.post('/api/auth/google/', credential='x')
        self.assertEqual((r1.status_code, r1.data['token']), (200, r2.data['token']))
        self.assertEqual(User.objects.filter(google_sub='g-1').count(), 1)
        v.return_value = {'sub': 'g-2', 'email': 'ann@example.com'}  # email существующего локального аккаунта
        self.assertEqual(self.post('/api/auth/google/', credential='x').status_code, 409)

    @patch('accounts.google_auth.verify')
    def test_link_and_unlink(self, v):
        v.return_value = {'sub': 'g-3', 'email': 'ann@gmail.com'}
        self.client.force_authenticate(self.u)
        self.assertEqual(self.post('/api/auth/google/link/', credential='x').status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me/').data['google_email'], 'ann@gmail.com')
        self.client.force_authenticate(self.mk('bob'))
        self.assertEqual(self.post('/api/auth/google/link/', credential='x').status_code, 409)  # уже занят
        self.client.force_authenticate(self.u)
        self.assertEqual(self.post('/api/auth/google/unlink/').status_code, 200)
        g = User(username='gonly', google_sub='g-9')
        g.set_unusable_password()
        g.save()
        self.client.force_authenticate(g)
        self.assertEqual(self.post('/api/auth/google/unlink/').status_code, 409)  # без пароля отвязать нельзя


class ProfileTests(AuthBase):
    def test_registration_rules(self):
        ok = self.post('/api/auth/register/', username='kim', email='kim@example.com', password='Strong-pass-4711')
        self.assertEqual(ok.status_code, 201)
        self.assertIn('token', ok.data)
        dup = self.post('/api/auth/register/', username='kim2', email='KIM@example.com', password='Strong-pass-4711')
        self.assertEqual(dup.status_code, 400)
        self.assertIn('email', dup.data)
        self.assertIn('password', self.post('/api/auth/register/', username='kim3', email='k3@example.com', password='123').data)
        self.assertEqual(User.objects.get(username='kim').role, 'participant')

    def test_profile_phone_notification_toggle_and_role_is_protected(self):
        u = self.mk('ann')
        self.assertEqual(self.as_(u, '/api/auth/me/', 'patch', phone='abc').status_code, 400)
        r = self.as_(u, '/api/auth/me/', 'patch', phone='+996 555 123 456', notify_email=False, role='admin')
        self.assertEqual(r.status_code, 200)
        u.refresh_from_db()
        self.assertEqual((u.phone, u.notify_email, u.role), ('+996 555 123 456', False, 'participant'))  # роль не меняется
