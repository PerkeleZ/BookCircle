from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase


class BaseAPITest(APITestCase):
    """Общая основа тестов: чистый кэш, фабрика пользователей и короткие вызовы API."""

    def setUp(self):
        super().setUp()
        cache.clear()

    def mk(self, name, **kw):
        return get_user_model().objects.create_user(name, email=f'{name}@example.com', password='x12345678', **kw)

    def as_(self, user, url, method='post', **data):
        self.client.force_authenticate(user)
        return getattr(self.client, method)(url, data, format='json')

    def anon(self, url):
        self.client.force_authenticate(None)
        return self.client.get(url)
