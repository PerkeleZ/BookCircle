from common.testing import BaseAPITest
from catalog.models import Book


class StatsTests(BaseAPITest):
    def test_staff_stats_permissions_and_shape(self):
        u, mod = self.mk('u'), self.mk('mod', role='moderator')
        Book.objects.create(title='К', author='А', genre='Роман')
        self.assertEqual(self.as_(u, '/api/stats/', 'get').status_code, 403)
        self.assertEqual(self.anon('/api/stats/').status_code, 401)
        d = self.as_(mod, '/api/stats/', 'get').data
        self.assertEqual(d['books']['approved'], 1)
        self.assertEqual(len(d['series']['new_users']), 8)
        self.assertEqual(sum(w['count'] for w in d['series']['new_users']), 2)  # u и mod зарегистрированы только что

    def test_public_stats_are_open(self):
        r = self.anon('/api/stats/public/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.data), {'books', 'members', 'exchanges', 'reviews'})
