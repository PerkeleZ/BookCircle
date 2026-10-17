from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Book, Copy, Loan, Review, User


class BookCircleTests(APITestCase):
    def setUp(self):
        mk = lambda n, **kw: User.objects.create_user(n, password='x12345678', **kw)
        self.o1, self.o2, self.b1, self.b2 = mk('o1'), mk('o2'), mk('b1'), mk('b2')
        self.mod = mk('mod', role='moderator')
        self.book = Book.objects.create(title='Тест', author='Автор', genre='Роман')
        self.c1 = Copy.objects.create(book=self.book, owner=self.o1, pickup_place='A')
        self.c2 = Copy.objects.create(book=self.book, owner=self.o2, pickup_place='B')
        self.due = (timezone.localdate() + timedelta(days=7)).isoformat()

    def act(self, user, url, method='post', **data):
        self.client.force_authenticate(user)
        return getattr(self.client, method)(url, data, format='json')

    def req(self, user, copy, date=None):
        return self.act(user, f'/api/copies/{copy.id}/loans/', requested_return_date=date or self.due, phone='+996 555 123 456')

    def loan_act(self, user, loan_id, action):
        return self.act(user, f'/api/loans/{loan_id}/{action}/')

    def available(self):
        self.client.force_authenticate(None)
        return self.client.get(f'/api/books/{self.book.id}/').data['available_copies']

    def test_two_copies_book_independently(self):
        l1, l2 = self.req(self.b1, self.c1).data['id'], self.req(self.b2, self.c2).data['id']
        self.assertEqual(self.loan_act(self.o1, l1, 'accept').status_code, 200)
        self.assertEqual(self.loan_act(self.o2, l2, 'accept').status_code, 200)
        self.assertEqual(self.available(), 0)

    def test_full_cycle_restores_availability(self):
        self.assertEqual(self.available(), 2)
        lid = self.req(self.b1, self.c1).data['id']
        self.loan_act(self.o1, lid, 'accept')
        self.assertEqual(self.available(), 1)
        self.assertEqual(self.loan_act(self.o1, lid, 'hand-over').data['status'], 'handed_over')
        self.assertEqual(self.loan_act(self.o1, lid, 'return').data['status'], 'returned')
        self.assertEqual(self.available(), 2)

    def test_cannot_accept_two_borrowers(self):
        l1, l2 = self.req(self.b1, self.c1).data['id'], self.req(self.b2, self.c1).data['id']
        self.assertEqual(self.loan_act(self.o1, l1, 'accept').status_code, 200)
        self.assertEqual(Loan.objects.get(pk=l2).status, 'rejected')  # второй отклонён автоматически
        self.assertEqual(self.loan_act(self.o1, l2, 'accept').status_code, 409)
        with self.assertRaises(IntegrityError), transaction.atomic():  # и на уровне БД
            Loan.objects.create(copy=self.c1, borrower=self.b2, status='accepted', requested_return_date=self.due)

    def test_review_edit_changes_rating_without_duplicate(self):
        url = f'/api/books/{self.book.id}/review/'
        self.act(self.b1, url, 'put', score=5, text='ок')
        self.act(self.b1, url, 'put', score=3, text='хм')
        self.assertEqual(Review.objects.count(), 1)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(f'/api/books/{self.book.id}/').data['avg_rating'], 3.0)
        self.act(self.b2, url, 'put', score=1)
        rid = Review.objects.get(user=self.b2).id
        self.assertEqual(self.act(self.mod, f'/api/reviews/{rid}/', 'patch', is_hidden=True).status_code, 200)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(f'/api/books/{self.book.id}/').data['avg_rating'], 3.0)  # скрытый не учтён

    def test_permissions_validation_and_transitions(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/loans/').status_code, 401)
        self.assertEqual(self.req(self.o1, self.c1).status_code, 400)  # своя книга
        self.assertEqual(self.req(self.b1, self.c1, '2000-01-01').status_code, 400)  # прошлая дата
        lid = self.req(self.b1, self.c1).data['id']
        self.assertEqual(self.loan_act(self.b2, lid, 'accept').status_code, 403)  # не владелец
        self.assertEqual(self.loan_act(self.o1, lid, 'return').status_code, 409)  # недопустимый переход
        self.loan_act(self.o1, lid, 'accept')
        r = self.act(self.o1, f'/api/copies/{self.c1.id}/', 'patch', is_active=False)
        self.assertEqual(r.status_code, 409)  # занятый экземпляр нельзя скрыть
        self.assertEqual(self.act(self.b1, '/api/reviews/', 'get').status_code, 403)  # только модератор


import re
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache


class AuthExtrasTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.u = User.objects.create_user('ann', email='ann@example.com', password='Old-pass-12345')

    def post(self, url, **data):
        return self.client.post(url, data, format='json')

    def test_password_reset_code_flow(self):
        confirm = '/api/auth/password-reset/confirm/'
        self.assertEqual(self.post('/api/auth/password-reset/', email='ANN@example.com').status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        code = re.search(r'код для сброса пароля: (\d{6})', body).group(1)
        self.assertIn(f'#/reset?email=ann%40example.com&code={code}', body)  # ссылка с кодом
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
        code = re.search(r'код для сброса пароля: (\d{6})', mail.outbox[0].body).group(1)
        wrong = '000000' if code != '000000' else '111111'
        for _ in range(5):
            self.assertEqual(self.post(confirm, email='ann@example.com', code=wrong, password='New-pass-98765').status_code, 400)
        self.assertEqual(self.post(confirm, email='ann@example.com', code=code, password='New-pass-98765').status_code, 400)

    @patch('core.google_auth.verify')
    def test_google_login_creates_reuses_and_never_autolinks(self, v):
        v.return_value = {'sub': 'g-1', 'email': 'new@example.com'}
        r1, r2 = self.post('/api/auth/google/', credential='x'), self.post('/api/auth/google/', credential='x')
        self.assertEqual((r1.status_code, r1.data['token']), (200, r2.data['token']))
        self.assertEqual(User.objects.filter(google_sub='g-1').count(), 1)
        v.return_value = {'sub': 'g-2', 'email': 'ann@example.com'}  # email существующего локального аккаунта
        self.assertEqual(self.post('/api/auth/google/', credential='x').status_code, 409)

    @patch('core.google_auth.verify')
    def test_link_and_unlink(self, v):
        v.return_value = {'sub': 'g-3', 'email': 'ann@gmail.com'}
        self.client.force_authenticate(self.u)
        self.assertEqual(self.post('/api/auth/google/link/', credential='x').status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me/').data['google_email'], 'ann@gmail.com')
        self.client.force_authenticate(User.objects.create_user('bob', email='bob@example.com', password='x'))
        self.assertEqual(self.post('/api/auth/google/link/', credential='x').status_code, 409)  # уже занят
        self.client.force_authenticate(self.u)
        self.assertEqual(self.post('/api/auth/google/unlink/').status_code, 200)
        g = User(username='gonly', google_sub='g-9')
        g.set_unusable_password()
        g.save()
        self.client.force_authenticate(g)
        self.assertEqual(self.post('/api/auth/google/unlink/').status_code, 409)  # без пароля отвязать нельзя

    def test_reset_dev_hints_and_mail_failure(self):
        from django.test import override_settings
        with override_settings(DEBUG=True):  # в разработке неизвестный email — явная подсказка, а не молчание
            self.assertEqual(self.post('/api/auth/password-reset/', email='nobody@gmail.com').status_code, 404)
        with patch('core.views.send_mail', side_effect=OSError('smtp down')):
            self.assertEqual(self.post('/api/auth/password-reset/', email='ann@example.com').status_code, 503)


from core.models import Meeting, ReadingEntry


class FeatureTests(APITestCase):
    def setUp(self):
        cache.clear()
        mk = lambda n, **kw: User.objects.create_user(n, email=f'{n}@example.com', password='x12345678', **kw)
        self.a, self.b, self.c, self.mod = mk('a'), mk('b'), mk('c'), mk('mod', role='moderator')
        self.horror = Book.objects.create(title='Оно', author='Стивен Кинг', genre='Ужасы')
        self.horror2 = Book.objects.create(title='Зов Ктулху', author='Говард Лавкрафт', genre='Ужасы')
        self.it = Book.objects.create(title='Чистый код', author='Роберт Мартин', genre='Учебники и пособия по IT')
        self.novel = Book.objects.create(title='Война и мир', author='Лев Толстой', genre='Роман')
        self.soon = (timezone.now() + timedelta(days=2)).isoformat()

    def as_(self, user, url, method='post', **data):
        self.client.force_authenticate(user)
        return getattr(self.client, method)(url, data, format='json')

    def test_genres_include_new_ones(self):
        self.client.force_authenticate(None)
        g = self.client.get('/api/genres/').data['results']
        self.assertIn('Ужасы', g)
        self.assertIn('Учебники и пособия по IT', g)

    def test_own_review_can_be_edited(self):
        url = f'/api/books/{self.horror.id}/review/'
        r = self.as_(self.a, url, 'put', score=5, text='страшно')
        self.assertEqual((r.status_code, r.data['created']), (201, True))
        r = self.as_(self.a, url, 'put', score=4, text='страшно, но затянуто')
        self.assertEqual((r.status_code, r.data['created']), (200, False))
        mine = self.as_(self.a, f'/api/books/{self.horror.id}/', 'get').data['reviews']
        self.assertEqual([(x['is_mine'], x['text'], x['score']) for x in mine], [(True, 'страшно, но затянуто', 4)])
        theirs = self.as_(self.b, f'/api/books/{self.horror.id}/', 'get').data['reviews']
        self.assertFalse(theirs[0]['is_mine'])
        self.assertEqual(Review.objects.count(), 1)

    def test_meetings_rules(self):
        base = dict(title='Обсуждение', book_id=self.horror.id, place='Библиотека', capacity=2)
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
        past = Meeting.objects.create(title='Было', organizer=self.a, place='X',
                                      starts_at=timezone.now() - timedelta(days=1))
        self.assertEqual(self.as_(self.b, f'/api/meetings/{past.id}/join/').status_code, 409)  # прошла
        self.assertEqual(self.as_(self.b, '/api/meetings/?when=past', 'get').data['count'], 1)

    def test_reading_goals_progress(self):
        self.assertEqual(self.as_(self.a, '/api/goals/', 'put', period='year', target=0).status_code, 400)
        self.assertEqual(self.as_(self.a, '/api/goals/', 'put', period='week', target=3).status_code, 400)
        g = self.as_(self.a, '/api/goals/', 'put', period='year', target=2).data
        self.assertEqual((g['year']['done'], g['year']['percent'], g['month']), (0, 0, None))
        self.as_(self.a, f'/api/reading/{self.horror.id}/', 'put', status='done')
        self.as_(self.a, '/api/goals/', 'put', period='month', target=1)
        g = self.as_(self.a, '/api/goals/', 'get').data
        self.assertEqual((g['year']['done'], g['year']['percent']), (1, 50))
        self.assertTrue(g['month']['achieved'])
        self.assertEqual(self.as_(self.a, '/api/goals/year/', 'delete').status_code, 204)
        self.assertIsNone(self.as_(self.a, '/api/goals/', 'get').data['year'])

    def test_genre_recommendations(self):
        ReadingEntry.objects.create(user=self.a, book=self.horror, status='done', finished_at=timezone.localdate())
        r = self.as_(self.a, '/api/recommendations/', 'get').data
        titles = [b['title'] for b in r['results']]
        self.assertEqual(r['genres'][0]['genre'], 'Ужасы')
        self.assertEqual(titles[0], 'Зов Ктулху')  # тот же жанр, ещё не читал
        self.assertNotIn('Оно', titles)  # уже прочитано
        self.assertNotIn('Война и мир', titles)  # чужой жанр
        self.assertIn('Ужасы', r['results'][0]['reason'])
        cold = self.as_(self.b, '/api/recommendations/', 'get').data  # нет данных — популярное в клубе
        self.assertEqual(cold['genres'], [])
        self.assertTrue(cold['results'])


class ModerationAndRentalTests(APITestCase):
    def setUp(self):
        cache.clear()
        mk = lambda n, **kw: User.objects.create_user(n, email=f'{n}@example.com', password='x12345678', **kw)
        self.u, self.v, self.mod = mk('u'), mk('v'), mk('mod', role='moderator')
        self.admin = User.objects.create_superuser('boss', 'boss@example.com', 'x12345678')
        self.book = Book.objects.create(title='Старая', author='Автор', genre='Роман')
        self.due = (timezone.localdate() + timedelta(days=5)).isoformat()

    def as_(self, user, url, method='post', **data):
        self.client.force_authenticate(user)
        return getattr(self.client, method)(url, data, format='json')

    def anon(self, url):
        self.client.force_authenticate(None)
        return self.client.get(url)

    def test_user_submission_requires_moderation(self):
        r = self.as_(self.u, '/api/books/', title='Новая', author='Автор Н', genre='Ужасы', description='d')
        self.assertEqual((r.status_code, r.data['status']), (201, 'pending'))
        bid = r.data['id']
        self.assertEqual(self.anon('/api/books/').data['count'], 1)  # на сайте не видна
        self.assertEqual(self.anon(f'/api/books/{bid}/').status_code, 404)
        self.assertEqual(self.as_(self.v, f'/api/books/{bid}/', 'get').status_code, 404)  # чужим тоже
        self.assertEqual(self.as_(self.u, f'/api/books/{bid}/', 'get').status_code, 200)  # автору видна
        self.assertEqual(self.as_(self.u, '/api/submissions/', 'get').data['books'][0]['status'], 'pending')
        self.assertEqual(self.as_(self.u, f'/api/moderation/books/{bid}/approve/').status_code, 403)
        self.assertEqual(self.as_(self.mod, f'/api/moderation/books/{bid}/approve/').status_code, 200)
        self.assertEqual(self.anon('/api/books/').data['count'], 2)
        self.assertEqual(self.as_(self.mod, '/api/books/', title='От модератора', author='М', genre='Роман').data['status'], 'approved')
        self.assertEqual(self.as_(self.v, '/api/books/', title='старая', author='АВТОР', genre='Роман').status_code, 400)  # дубликат

    def test_reject_and_resubmit(self):
        bid = self.as_(self.u, '/api/books/', title='Спорная', author='А', genre='Роман').data['id']
        r = self.as_(self.mod, f'/api/moderation/books/{bid}/reject/', reason='Нет описания')
        self.assertEqual(r.data['status'], 'rejected')
        mine = self.as_(self.u, '/api/submissions/', 'get').data['books'][0]
        self.assertEqual((mine['status'], mine['reject_reason']), ('rejected', 'Нет описания'))
        self.assertEqual(self.anon('/api/books/').data['count'], 1)
        r = self.as_(self.u, f'/api/books/{bid}/', 'patch', description='Добавил описание')
        self.assertEqual((r.status_code, r.data['status']), (200, 'pending'))
        self.assertEqual(self.as_(self.v, f'/api/books/{bid}/', 'patch', description='x').status_code, 404)  # чужой черновик не виден

    def test_edit_proposals(self):
        url = f'/api/books/{self.book.id}/edits/'
        self.assertEqual(self.as_(self.u, url, title='Старая', author='Автор', genre='Роман').status_code, 400)  # без изменений
        r = self.as_(self.u, url, title='Старая', author='Автор', genre='Классика', description='Новое описание')
        self.assertEqual((r.status_code, r.data['status']), (201, 'pending'))
        self.book.refresh_from_db()
        self.assertEqual(self.book.genre, 'Роман')  # правка ещё не применена
        self.assertEqual(self.as_(self.u, f'/api/books/{self.book.id}/', 'patch', genre='X').status_code, 403)
        self.assertEqual(len(self.as_(self.mod, '/api/moderation/edits/', 'get').data['results']), 1)
        self.assertEqual(self.as_(self.mod, f'/api/moderation/edits/{r.data["id"]}/approve/').status_code, 200)
        self.book.refresh_from_db()
        self.assertEqual((self.book.genre, self.book.description), ('Классика', 'Новое описание'))

    def test_delete_rules_for_reviews(self):
        url = f'/api/books/{self.book.id}/review/'
        self.as_(self.u, url, 'put', score=4, text='ok')
        self.as_(self.v, url, 'put', score=5, text='ok2')
        rid = Review.objects.get(user=self.v).id
        self.assertEqual(self.as_(self.mod, f'/api/reviews/{rid}/', 'delete').status_code, 403)  # модератор только скрывает
        self.assertEqual(self.as_(self.mod, f'/api/reviews/{rid}/', 'patch', is_hidden=True).status_code, 200)
        self.assertEqual(self.as_(self.admin, f'/api/reviews/{rid}/', 'delete').status_code, 204)
        self.assertEqual(self.as_(self.u, url, 'delete').status_code, 204)  # свой отзыв
        self.assertEqual(self.as_(self.u, url, 'delete').status_code, 404)
        self.assertEqual(Review.objects.count(), 0)

    def test_admin_deletes_books(self):
        copy = Copy.objects.create(book=self.book, owner=self.u, pickup_place='A')
        loan = Loan.objects.create(copy=copy, borrower=self.v, status='accepted', borrower_phone='+996 555 000 111',
                                   requested_return_date=timezone.localdate() + timedelta(days=5))
        url = f'/api/books/{self.book.id}/'
        self.assertEqual(self.as_(self.mod, url, 'delete').status_code, 403)
        self.assertEqual(self.as_(self.u, url, 'delete').status_code, 403)
        self.assertEqual(self.as_(self.admin, url, 'delete').status_code, 409)  # есть активная передача
        loan.status = 'returned'
        loan.save()
        self.assertEqual(self.as_(self.admin, url, 'delete').status_code, 204)
        self.assertFalse(Book.objects.filter(pk=self.book.id).exists() or Copy.objects.exists() or Loan.objects.exists())
        own = self.as_(self.u, '/api/books/', title='Моя', author='А', genre='Роман').data['id']
        self.assertEqual(self.as_(self.u, f'/api/books/{own}/', 'delete').status_code, 204)  # свою неодобренную — можно

    def test_hide_book(self):
        copy = Copy.objects.create(book=self.book, owner=self.u, pickup_place='A')
        url = f'/api/books/{self.book.id}/'
        self.assertEqual(self.as_(self.u, url + 'hide/').status_code, 403)
        self.assertEqual(self.as_(self.mod, url + 'hide/').data['status'], 'hidden')
        self.assertEqual(self.anon('/api/books/').data['count'], 0)
        self.assertEqual(self.as_(self.v, '/api/copies/', 'get').data['count'], 0)
        r = self.as_(self.v, f'/api/copies/{copy.id}/loans/', requested_return_date=self.due, phone='+996 555 123 456')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.as_(self.mod, url + 'unhide/').data['status'], 'approved')

    def test_half_star_ratings(self):
        url = f'/api/books/{self.book.id}/review/'
        self.assertEqual(self.as_(self.u, url, 'put', score=3.5, text='').status_code, 201)
        for bad in (3.3, 0.5, 5.5):
            self.assertEqual(self.as_(self.u, url, 'put', score=bad).status_code, 400)
        self.as_(self.v, url, 'put', score=4.5)
        self.assertEqual(self.anon(f'/api/books/{self.book.id}/').data['avg_rating'], 4.0)
        self.assertEqual(self.as_(self.u, f'/api/books/{self.book.id}/', 'get').data['my_review']['score'], 3.5)

    def test_phone_required_and_rental_alerts(self):
        copy = Copy.objects.create(book=self.book, owner=self.u, pickup_place='A')
        url = f'/api/copies/{copy.id}/loans/'
        self.assertIn('phone', self.as_(self.v, url, requested_return_date=self.due).data)  # без телефона
        self.assertIn('phone', self.as_(self.v, url, requested_return_date=self.due, phone='abc').data)
        r = self.as_(self.v, url, requested_return_date=self.due, phone='+996 555 123 456')
        self.assertEqual(r.status_code, 201)
        lid = r.data['id']
        owner_view = self.as_(self.u, '/api/loans/?box=incoming', 'get').data['results'][0]
        self.assertEqual((owner_view['borrower_phone'], owner_view['owner_phone']), ('+996 555 123 456', ''))
        self.u.phone = '+996 700 111 222'
        self.u.save()
        self.as_(self.u, f'/api/loans/{lid}/accept/')
        self.as_(self.u, f'/api/loans/{lid}/hand-over/')
        mine = self.as_(self.v, '/api/loans/?box=outgoing', 'get').data['results'][0]
        self.assertEqual((mine['owner_phone'], mine['days_left']), ('+996 700 111 222', 5))
        self.assertEqual(self.as_(self.v, '/api/alerts/', 'get').data['count'], 0)  # срок ещё далеко
        Loan.objects.filter(pk=lid).update(requested_return_date=timezone.localdate() - timedelta(days=3))
        for who, role in ((self.v, 'borrower'), (self.u, 'owner')):  # просрочка видна обеим сторонам
            a = self.as_(who, '/api/alerts/', 'get').data
            self.assertEqual((a['overdue'], a['results'][0]['role'], a['results'][0]['days_left']), (1, role, -3))
        self.assertEqual(self.as_(self.mod, '/api/alerts/', 'get').data['count'], 0)
        self.assertEqual(len(self.as_(self.u, '/api/loans/?box=active', 'get').data['results']), 1)

    def test_book_options_return_every_approved_book(self):
        for i in range(30):
            Book.objects.create(title=f'К{i}', author='А', genre='Роман')
        pend = Book.objects.create(title='Черновик', author='А', genre='Роман', status='pending')
        r = self.as_(self.u, '/api/books/options/', 'get').data['results']
        self.assertEqual(len(r), 31)  # 30 новых + «Старая»; книга на модерации не попадает
        body = dict(book_id=pend.id, condition='good', pickup_place='A')
        self.assertEqual(self.as_(self.u, '/api/copies/', **body).status_code, 400)
