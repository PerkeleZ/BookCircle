"""Нагрузочный тест (Locust): pip install locust && locust -f loadtest/locustfile.py --host http://localhost:8000
Профиль: 80 % гостей листают каталог и книги, 20 % участников входят и работают со своей полкой и уведомлениями."""
import random

from locust import HttpUser, between, task


class Guest(HttpUser):
    weight = 4
    wait_time = between(1, 3)

    @task(5)
    def catalog(self):
        self.client.get('/api/books/?page=1&page_size=8', name='/api/books/')

    @task(3)
    def search(self):
        self.client.get('/api/books/?search=' + random.choice(['кинг', 'война', 'код', 'айтматов']), name='/api/books/?search')

    @task(3)
    def book_page(self):
        pk = random.randint(1, 15)
        for part in ('', 'copies/', 'reviews/'):
            self.client.get(f'/api/books/{pk}/{part}', name=f'/api/books/:id/{part}')

    @task(1)
    def public(self):
        self.client.get('/api/genres/')
        self.client.get('/api/stats/public/')

    @task(1)
    def static(self):
        self.client.get('/', name='/ (SPA)')


class Member(HttpUser):
    weight = 1
    wait_time = between(1, 4)

    def on_start(self):
        r = self.client.post('/api/auth/login/', json={'username': random.choice(['aida', 'bakyt', 'nurlan', 'aigerim', 'timur']), 'password': 'pass12345'})
        self.client.headers['Authorization'] = 'Token ' + r.json().get('token', '')

    @task(3)
    def alerts(self):
        self.client.get('/api/alerts/')
        self.client.get('/api/notifications/unread-count/')

    @task(2)
    def my_shelf(self):
        self.client.get('/api/copies/?mine=1')
        self.client.get('/api/books/options/')

    @task(2)
    def loans(self):
        self.client.get('/api/loans/?box=incoming')
        self.client.get('/api/loans/?box=active')

    @task(1)
    def recommendations(self):
        self.client.get('/api/recommendations/')
