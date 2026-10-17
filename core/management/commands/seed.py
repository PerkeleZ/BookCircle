from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import (Book, BookEdit, Copy, Loan, Meeting, MeetingParticipant, ReadingEntry, ReadingGoal, Review, User)

BOOKS = [
    ('Джамиля', 'Чингиз Айтматов', 'Классика', 'Повесть о любви, свободе и выборе в киргизском айыле.'),
    ('Белый пароход', 'Чингиз Айтматов', 'Классика', 'Мальчик верит в легенду и сталкивается с жестокостью взрослого мира.'),
    ('Война и мир', 'Лев Толстой', 'Роман', 'Эпопея о судьбах нескольких семей на фоне наполеоновских войн.'),
    ('Мастер и Маргарита', 'Михаил Булгаков', 'Роман', 'Дьявол приезжает в Москву 1930-х, а рядом разворачивается история Пилата.'),
    ('Пикник на обочине', 'Аркадий и Борис Стругацкие', 'Фантастика', 'Сталкеры добывают артефакты в Зоне, оставленной пришельцами.'),
    ('Солярис', 'Станислав Лем', 'Фантастика', 'Учёные пытаются понять разум океана на далёкой планете.'),
    ('Убийство в «Восточном экспрессе»', 'Агата Кристи', 'Детектив', 'Пуаро ищет убийцу среди пассажиров поезда, застрявшего в снегах.'),
    ('Космос', 'Карл Саган', 'Научпоп', 'Путешествие по истории астрономии и месту человека во Вселенной.'),
    ('Евгений Онегин', 'Александр Пушкин', 'Поэзия', 'Роман в стихах о любви, гордости и упущенных возможностях.'),
    ('Sapiens. Краткая история человечества', 'Юваль Ной Харари', 'История', 'Как Homo sapiens стал доминирующим видом на планете.'),
    ('Зов Ктулху', 'Говард Лавкрафт', 'Ужасы', 'Рассказ о тайном культе и древнем божестве: правда о мироздании сводит с ума.'),
    ('Сияние', 'Стивен Кинг', 'Ужасы', 'Зимний смотритель горного отеля теряет рассудок, а дом охотится на его семью.'),
    ('Оно', 'Стивен Кинг', 'Ужасы', 'Друзья возвращаются в родной городок, чтобы снова встретиться со злом из детства.'),
    ('Чистый код', 'Роберт Мартин', 'Учебники и пособия по IT', 'Как писать понятный и поддерживаемый код: имена, функции, тесты, рефакторинг.'),
    ('Грокаем алгоритмы', 'Адитья Бхаргава', 'Учебники и пособия по IT', 'Иллюстрированное введение в алгоритмы и структуры данных на простых примерах.'),
]
PLACES = ['Общежитие №2, холл', 'Библиотека, 1 этаж', 'Корпус А, столовая', 'Кафе у входа', 'Корпус Б, вахта']
REVIEWS = ['Перечитывал(а) дважды.', 'Сильная книга, рекомендую.', 'Не мог(ла) оторваться.', 'Местами затянуто.',
           'Хороший перевод.', 'Классика не зря.', 'Не понравилась концовка.', 'Отличный сюжет.',
           'Идеи актуальны до сих пор.', 'Читается легко.']


def make_user(name, pwd, **kw):
    u, _ = User.objects.get_or_create(username=name, defaults={'email': f'{name}@example.com', **kw})
    u.set_password(pwd)
    u.save()
    return u


class Command(BaseCommand):
    help = 'Демо-данные: 15 произведений, 20 экземпляров, 5 пользователей, 10 передач, 10 отзывов'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='очистить данные перед наполнением')

    @transaction.atomic
    def handle(self, *args, **o):
        if o['reset']:
            for m in (Loan, Review, ReadingEntry, ReadingGoal, Meeting, Copy, Book):
                m.objects.all().delete()
        elif Book.objects.exists():
            return self.stdout.write('Данные уже есть. Используйте --reset для пересоздания.')
        today, now = timezone.localdate(), timezone.now()
        make_user('admin', 'admin12345', is_staff=True, is_superuser=True)
        make_user('moder', 'moder12345', role='moderator')
        users = [make_user(n, 'pass12345') for n in ('aida', 'bakyt', 'nurlan', 'aigerim', 'timur')]
        for i, u in enumerate(users):
            u.phone = f'+996 555 {100 + i} {200 + i}'
            u.save()
        books = [Book.objects.create(title=t, author=a, genre=g, description=d) for t, a, g, d in BOOKS]
        conds = ['new', 'good', 'fair', 'worn']
        copies = []
        for i in range(20):  # книги 0–4 имеют второй экземпляр у другого владельца
            owner = users[i % 5] if i < 15 else users[(i + 2) % 5]
            copies.append(Copy.objects.create(book=books[i % 15], owner=owner, condition=conds[i % 4],
                                              pickup_place=PLACES[i % 5]))
        plan = [S for S in [Loan.Status.RETURNED] * 4 + [Loan.Status.HANDED_OVER] * 2 + [Loan.Status.ACCEPTED]
                + [Loan.Status.PENDING] * 2 + [Loan.Status.REJECTED]]
        for i, st in enumerate(plan):
            c = copies[i]
            kw = {}
            if st in (Loan.Status.RETURNED, Loan.Status.HANDED_OVER):
                kw['handed_at'] = now - timedelta(days=20)
            if st == Loan.Status.RETURNED:
                kw['returned_at'] = now - timedelta(days=3)
            borrower = users[(users.index(c.owner) + 1) % 5]
            Loan.objects.create(copy=c, borrower=borrower, borrower_phone=borrower.phone, status=st,
                                requested_return_date=today + timedelta(days=-5 if i == 4 else 10 + i), **kw)
        for i, score in enumerate([5, 4.5, 5, 3.5, 4, 5, 2.5, 4.5, 5, 3.5]):
            Review.objects.create(user=users[(i + 1) % 5], book=books[i], score=score, text=REVIEWS[i],
                                  is_hidden=(i == 6))
        for j, u in enumerate(users):
            for k, st in enumerate(['done', 'reading', 'want']):
                ReadingEntry.objects.create(user=u, book=books[(j * 3 + k) % 15], status=st,
                                            finished_at=today.replace(day=1) if st == 'done' else None)
        def meeting(title, desc, book, org, delta, place, cap, guests):
            m = Meeting.objects.create(title=title, description=desc, book=book, organizer=org, starts_at=now + delta,
                                       place=place, capacity=cap)
            for u in [org] + guests:
                MeetingParticipant.objects.create(meeting=m, user=u)

        meeting('Обсуждаем «Сияние»', 'Читаем вместе и говорим о страхе, одиночестве и доме, который «живёт».', books[11],
                users[0], timedelta(days=3), 'Библиотека, читальный зал', 8, users[1:3])
        meeting('Клуб программиста: «Чистый код»', 'Разбираем главу про функции и имена на живых примерах.', books[13],
                users[1], timedelta(days=7), 'Корпус Б, аудитория 204', None, users[3:5])
        meeting('Вечер Айтматова', 'Читаем отрывки из «Джамили».', books[0], users[2], timedelta(days=-10),
                'Общежитие №2, холл', 10, users[:2])
        ReadingGoal.objects.create(user=users[0], year=today.year, month=0, target=12)
        ReadingGoal.objects.create(user=users[0], year=today.year, month=today.month, target=2)
        ReadingGoal.objects.create(user=users[1], year=today.year, month=0, target=20)
        # демо для модерации: книга от участника и предложенная правка
        Book.objects.create(title='Хоббит', author='Дж. Р. Р. Толкин', genre='Фантастика', created_by=users[2],
                            status=Book.Status.PENDING, description='Путешествие Бильбо Бэггинса к Одинокой горе.')
        BookEdit.objects.create(book=books[7], proposed_by=users[3], title='Космос', author='Карл Саган',
                                genre='Научпоп', description='Рассказ о космосе, науке и месте человечества во Вселенной.')
        self.stdout.write(self.style.SUCCESS('Готово. Аккаунты: admin/admin12345, moder/moder12345, '
                                             'aida|bakyt|nurlan|aigerim|timur / pass12345'))
