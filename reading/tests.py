from django.utils import timezone

from common.testing import BaseAPITest
from catalog.models import Book

from .models import ReadingEntry


class ReadingTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.a, self.b = self.mk('a'), self.mk('b')
        self.horror = Book.objects.create(title='Оно', author='Стивен Кинг', genre='Ужасы')
        self.horror2 = Book.objects.create(title='Зов Ктулху', author='Говард Лавкрафт', genre='Ужасы')
        self.it = Book.objects.create(title='Чистый код', author='Роберт Мартин', genre='Учебники и пособия по IT')
        self.novel = Book.objects.create(title='Война и мир', author='Лев Толстой', genre='Роман')

    def test_reading_status_roundtrip_and_finished_date(self):
        url = f'/api/reading/{self.horror.id}/'
        self.assertIsNone(self.as_(self.a, url, 'get').data['status'])
        r = self.as_(self.a, url, 'put', status='done')
        self.assertEqual(r.data['finished_at'], timezone.localdate().isoformat())  # дата проставляется сама
        self.assertEqual(self.as_(self.a, url, 'get').data['status'], 'done')
        self.assertEqual(self.as_(self.a, url, 'put', status='reading').data['finished_at'], None)
        self.assertEqual(self.as_(self.a, url, 'put', status='done', finished_at='2999-01-01').status_code, 400)

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
