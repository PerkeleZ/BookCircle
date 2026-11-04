import json
import logging

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from .cache import bump, cached


class HealthTests(TestCase):
    def test_healthz_and_readyz(self):
        self.assertEqual(self.client.get('/healthz').json(), {'status': 'ok'})
        r = self.client.get('/readyz')
        self.assertEqual((r.status_code, r.json()['checks']), (200, {'database': 'ok', 'cache': 'ok'}))

    def test_request_id_is_echoed_or_generated(self):
        self.assertEqual(self.client.get('/healthz', HTTP_X_REQUEST_ID='abc123')['X-Request-ID'], 'abc123')
        self.assertEqual(len(self.client.get('/healthz')['X-Request-ID']), 12)


class CacheHelperTests(SimpleTestCase):
    def test_versioned_cache_is_invalidated_by_bump(self):
        cache.clear()
        calls = []
        produce = lambda: calls.append(1) or len(calls)
        self.assertEqual((cached('ns', 'k', 60, produce), cached('ns', 'k', 60, produce)), (1, 1))  # второй вызов — из кэша
        bump('ns')
        self.assertEqual(cached('ns', 'k', 60, produce), 2)


class JsonLogTests(SimpleTestCase):
    def test_json_formatter_outputs_one_json_object(self):
        from .logs import JsonFormatter
        rec = logging.LogRecord('x', logging.INFO, 'f', 1, 'привет %s', ('мир',), None)
        rec.request_id = 'r1'
        data = json.loads(JsonFormatter().format(rec))
        self.assertEqual((data['msg'], data['request_id'], data['level']), ('привет мир', 'r1', 'INFO'))
