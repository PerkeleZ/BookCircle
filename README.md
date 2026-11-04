# BookCircle — платформа обмена книгами и книжных клубов

Участники делятся личными книгами, договариваются об обмене со сроком и контактами, ходят на книжные встречи, ставят цели чтения и получают рекомендации.
Модульный монолит на Django + DRF с лёгким интерфейсом на Bootstrap/Tailwind (без сборщика), готовый к запуску в Docker и к масштабированию.

## Быстрый старт

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed             # демоданные (без этого каталог пуст)
python manage.py runserver        # http://127.0.0.1:8000
```
**Docker (PostgreSQL + Redis + Celery + nginx):** `docker compose up --build` → http://localhost:8000.
Несколько экземпляров: `docker compose up -d --scale web=3 --scale worker=2`.

| Роль | Логин / пароль |
|---|---|
| Администратор (`/admin/`) | admin / admin12345 |
| Модератор | moder / moder12345 |
| Участники | aida, bakyt, nurlan, aigerim, timur / pass12345 |

Смените пароли и отключите демоданные (`SEED_DEMO=0`) до реального использования.

## Приложения

| Приложение | За что отвечает |
|---|---|
| `common` | ядро: права, исключения, кэш, логи, health-пробы |
| `accounts` | вход, регистрация, профиль, сброс пароля, Google |
| `catalog` | книги, жанры, модерация предложений и правок |
| `exchange` | полки, запросы, передачи, сроки, просрочка |
| `reviews` | отзывы и оценки (шаг 0,5) |
| `reading` | статусы чтения, цели, рекомендации |
| `meetings` | книжные встречи |
| `notifications` | уведомления на сайте и по email |
| `analytics`, `privacy` | показатели платформы; выгрузка и удаление данных |
| `demo`, `web` | демоданные; страница сайта, юридические страницы, статика |

Подробнее — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Документация
- [Архитектура](docs/ARCHITECTURE.md) · [Масштабирование и замеры](docs/SCALING.md) · [Эксплуатация](docs/OPERATIONS.md)
- [Продукт: готовность к продаже, тарифы, план](docs/PRODUCT.md) · [Сценарий демонстрации и питч](docs/DEMO_SCRIPT.md)
- [Соответствие исходному ТЗ](docs/SPEC_COVERAGE.md) · [Сторонние лицензии](THIRD_PARTY_NOTICES.md)
- Документация API: `/api/docs/` (Swagger), `/api/redoc/`, `/api/schema/`

## Команды
| | |
|---|---|
| `python manage.py test` | автотесты (быстрые настройки; SQLite или PostgreSQL+Redis через переменные) |
| `python manage.py seed --reset` | пересоздать демоданные |
| `python manage.py seed_bulk --books 2000` | нагрузочные данные |
| `python manage.py remind_overdue` | напоминания о просрочке вручную (то же делает ежедневная задача Celery) |
| `make assets` | пересобрать Tailwind/Bootstrap/шрифты (нужен Node.js) |
| `cd tests_ui && npm install && npm test` | проверки интерфейса в jsdom (сервер на :8140 с `seed`) |
