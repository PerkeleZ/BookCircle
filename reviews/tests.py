from common.testing import BaseAPITest
from catalog.models import Book
from notifications.models import Notification

from .models import Review


class ReviewTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.u, self.v, self.mod = self.mk('u'), self.mk('v'), self.mk('mod', role='moderator')
        self.admin = self.mk('boss', role='admin')
        self.book = Book.objects.create(title='Старая', author='Автор', genre='Роман')
        self.url = f'/api/books/{self.book.id}/review/'
        self.list_url = f'/api/books/{self.book.id}/reviews/'

    def test_own_review_can_be_edited_without_duplicates(self):
        r = self.as_(self.u, self.url, 'put', score=5, text='страшно')
        self.assertEqual((r.status_code, r.data['created']), (201, True))
        r = self.as_(self.u, self.url, 'put', score=4, text='страшно, но затянуто')
        self.assertEqual((r.status_code, r.data['created']), (200, False))
        mine = self.as_(self.u, self.list_url, 'get').data
        self.assertEqual([(x['is_mine'], x['text'], x['score']) for x in mine['results']], [(True, 'страшно, но затянуто', 4.0)])
        self.assertEqual(mine['my_review']['score'], 4.0)
        self.assertFalse(self.as_(self.v, self.list_url, 'get').data['results'][0]['is_mine'])
        self.assertEqual(Review.objects.count(), 1)

    def test_half_star_ratings(self):
        self.assertEqual(self.as_(self.u, self.url, 'put', score=3.5, text='').status_code, 201)
        for bad in (3.3, 0.5, 5.5):
            self.assertEqual(self.as_(self.u, self.url, 'put', score=bad).status_code, 400)
        self.as_(self.v, self.url, 'put', score=4.5)
        self.assertEqual(self.anon(f'/api/books/{self.book.id}/').data['avg_rating'], 4.0)
        self.assertEqual(self.as_(self.u, self.list_url, 'get').data['my_review']['score'], 3.5)

    def test_hidden_reviews_do_not_count_and_author_is_notified(self):
        self.as_(self.u, self.url, 'put', score=3)
        self.as_(self.v, self.url, 'put', score=1)
        rid = Review.objects.get(user=self.v).id
        self.assertEqual(self.as_(self.mod, f'/api/reviews/{rid}/', 'patch', is_hidden=True).status_code, 200)
        self.assertEqual(self.anon(f'/api/books/{self.book.id}/').data['avg_rating'], 3.0)  # скрытый не учтён
        self.assertTrue(Notification.objects.filter(user=self.v, kind='review_hidden').exists())
        self.assertEqual(self.anon(self.list_url).data['count'], 1)

    def test_delete_rules(self):
        self.as_(self.u, self.url, 'put', score=4, text='ok')
        self.as_(self.v, self.url, 'put', score=5, text='ok2')
        rid = Review.objects.get(user=self.v).id
        self.assertEqual(self.as_(self.mod, f'/api/reviews/{rid}/', 'delete').status_code, 403)  # модератор только скрывает
        self.assertEqual(self.as_(self.admin, f'/api/reviews/{rid}/', 'delete').status_code, 204)
        self.assertEqual(self.as_(self.u, self.url, 'delete').status_code, 204)  # свой отзыв
        self.assertEqual(self.as_(self.u, self.url, 'delete').status_code, 404)
        self.assertEqual(Review.objects.count(), 0)

    def test_moderation_list_is_staff_only_and_unapproved_books_have_no_reviews(self):
        self.assertEqual(self.as_(self.u, '/api/reviews/', 'get').status_code, 403)
        pend = Book.objects.create(title='Черновик', author='А', genre='Роман', status='pending')
        self.assertEqual(self.as_(self.u, f'/api/books/{pend.id}/review/', 'put', score=4).status_code, 404)
