from django.test import TestCase


class WebTests(TestCase):
    def test_index_uses_only_local_assets(self):
        html = self.client.get('/').content.decode()
        self.assertIn('web/js/core.js', html)
        self.assertIn('web/js/router.js', html)
        for external in ('cdn.jsdelivr', 'cdn.tailwindcss', 'fonts.googleapis', 'unpkg'):
            self.assertNotIn(external, html)  # без внешних зависимостей: быстрее, приватнее, работает офлайн

    def test_legal_pages(self):
        for page in ('terms', 'privacy'):
            self.assertEqual(self.client.get(f'/legal/{page}/').status_code, 200)
        self.assertEqual(self.client.get('/legal/nope/').status_code, 404)

    def test_api_docs_and_schema(self):
        self.assertEqual(self.client.get('/api/docs/').status_code, 200)
        r = self.client.get('/api/schema/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'BookCircle API', r.content)
        self.assertIn(b'/api/books/', r.content)
