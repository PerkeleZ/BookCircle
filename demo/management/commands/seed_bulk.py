import random
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from catalog.models import DEFAULT_GENRES, Book
from exchange.models import Copy, Loan
from reading.models import ReadingEntry
from reviews.models import Review


class Command(BaseCommand):
    help = 'Нагрузочные данные: тысячи книг с экземплярами, передачами, отзывами и отметками чтения (после обычного seed).'

    def add_arguments(self, parser):
        parser.add_argument('--books', type=int, default=2000)

    def handle(self, *args, **opts):
        users = list(User.objects.filter(role='participant', is_active=True)[:5])
        if len(users) < 3:
            raise CommandError('Сначала выполните: python manage.py seed')
        rnd, n, today = random.Random(7), opts['books'], timezone.localdate()
        start = Book.objects.count()
        books = Book.objects.bulk_create([
            Book(title=f'Нагрузочная книга {start + i}', author=f'Автор {i % 300}', genre=rnd.choice(DEFAULT_GENRES),
                 description='Тестовые данные для проверки производительности.',
                 search_text=f'нагрузочная книга {start + i} автор {i % 300}') for i in range(n)], batch_size=500)
        copies = Copy.objects.bulk_create([Copy(book=b, owner=rnd.choice(users), condition='good', pickup_place='Склад')
                                           for b in books for _ in range(rnd.randint(0, 4))], batch_size=500)
        loans = [Loan(copy=c, borrower=rnd.choice([u for u in users if u.id != c.owner_id]), status='returned',
                      requested_return_date=today - timedelta(days=rnd.randint(1, 90)), borrower_phone='+996 555 000 000')
                 for c in copies if rnd.random() < 0.4]
        Loan.objects.bulk_create(loans, batch_size=500)
        reviews = [Review(user=u, book=b, score=rnd.choice([2.5, 3, 3.5, 4, 4.5, 5]), text='Тестовый отзыв')
                   for b in books for u in rnd.sample(users, rnd.randint(0, len(users)))]
        Review.objects.bulk_create(reviews, batch_size=500)
        entries = [ReadingEntry(user=u, book=b, status=rnd.choice(['want', 'reading', 'done']), finished_at=today)
                   for b in rnd.sample(books, min(len(books), n // 2)) for u in rnd.sample(users, 2)]
        for e in entries:
            if e.status != 'done':
                e.finished_at = None
        ReadingEntry.objects.bulk_create(entries, batch_size=500)
        self.stdout.write(self.style.SUCCESS(f'Добавлено: книг {len(books)}, экземпляров {len(copies)}, передач {len(loans)}, отзывов {len(reviews)}, отметок чтения {len(entries)}'))
