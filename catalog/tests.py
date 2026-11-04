from common.testing import BaseAPITest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from notifications.models import Notification

from .models import Book


class CatalogTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.u, self.v, self.mod = self.mk('u'), self.mk('v'), self.mk('mod', role='moderator')
        self.book = Book.objects.create(title='Старая', author='Автор', genre='Роман')

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
        self.assertEqual(Notification.objects.get(user=self.u, kind='book_approved').link, f'#/book/{bid}')
        self.assertEqual(self.as_(self.mod, '/api/books/', title='От модератора', author='М', genre='Роман').data['status'], 'approved')
        self.assertEqual(self.as_(self.v, '/api/books/', title='старая', author='АВТОР', genre='Роман').status_code, 400)  # дубликат

    def test_reject_and_resubmit(self):
        bid = self.as_(self.u, '/api/books/', title='Спорная', author='А', genre='Роман').data['id']
        r = self.as_(self.mod, f'/api/moderation/books/{bid}/reject/', reason='Нет описания')
        self.assertEqual(r.data['status'], 'rejected')
        mine = self.as_(self.u, '/api/submissions/', 'get').data['books'][0]
        self.assertEqual((mine['status'], mine['reject_reason']), ('rejected', 'Нет описания'))
        self.assertEqual(Notification.objects.get(user=self.u, kind='book_rejected').body, 'Нет описания')
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
        self.assertTrue(Notification.objects.filter(user=self.u, kind='edit_approved').exists())

    def test_hide_and_unhide(self):
        url = f'/api/books/{self.book.id}/'
        self.assertEqual(self.as_(self.u, url + 'hide/').status_code, 403)
        self.assertEqual(self.as_(self.mod, url + 'hide/').data['status'], 'hidden')
        self.assertEqual(self.anon('/api/books/').data['count'], 0)
        self.assertEqual(self.as_(self.mod, url + 'unhide/').data['status'], 'approved')

    def test_moderation_queue_is_staff_only(self):
        self.assertEqual(self.as_(self.u, '/api/moderation/books/', 'get').status_code, 403)
        self.assertEqual(self.as_(self.mod, '/api/moderation/books/', 'get').status_code, 200)

    def test_genres_and_options_are_cached_and_invalidated(self):
        g = self.anon('/api/genres/').data['results']
        self.assertIn('Ужасы', g)
        self.assertIn('Учебники и пособия по IT', g)
        self.assertEqual(len(self.as_(self.u, '/api/books/options/', 'get').data['results']), 1)
        self.as_(self.mod, '/api/books/', title='Новая', author='А', genre='Киберпанк')  # создание сбрасывает кэш
        self.assertIn('Киберпанк', self.anon('/api/genres/').data['results'])
        self.assertEqual(len(self.as_(self.u, '/api/books/options/', 'get').data['results']), 2)
        pend = Book.objects.create(title='Черновик', author='А', genre='Роман', status='pending')
        titles = [b['title'] for b in self.as_(self.u, '/api/books/options/', 'get').data['results']]
        self.assertNotIn(pend.title, titles)  # неодобренные не попадают в списки выбора

    def test_options_server_side_search(self):
        for i in range(60):
            Book.objects.create(title=f'Том {i}', author='Автор', genre='Роман')
        r = self.as_(self.u, '/api/books/options/?q=ТОМ 5', 'get').data['results']
        self.assertTrue(0 < len(r) <= 50 and all('том 5' in b['title'].lower() for b in r))

    def test_search_is_case_insensitive_for_cyrillic_and_filters_by_genre(self):
        Book.objects.create(title='Война и мир', author='Лев Толстой', genre='Классика')
        self.assertEqual(self.anon('/api/books/?search=ВОЙНА').data['count'], 1)
        self.assertEqual(self.anon('/api/books/?search=толстой').data['count'], 1)
        self.assertEqual(self.anon('/api/books/?genre=Классика').data['count'], 1)

    def test_catalog_list_has_no_n_plus_one(self):
        Book.objects.bulk_create([Book(title=f'К{i}', author='А', genre='Роман', search_text=f'к{i} а') for i in range(25)])
        self.client.force_authenticate(None)
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get('/api/books/?page_size=25')
        self.assertEqual(r.data['count'], 26)
        self.assertLessEqual(len(ctx), 4, [q['sql'][:80] for q in ctx])
