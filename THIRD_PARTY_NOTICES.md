# Сторонние компоненты и их лицензии

Проект использует открытые компоненты. Перед коммерческим распространением сверьте актуальные условия лицензий.

| Компонент | Лицензия | Где используется |
|---|---|---|
| Django, Django REST framework, django-cors-headers, WhiteNoise | BSD-3-Clause / BSD | бэкенд |
| Celery, Redis-py, gunicorn, drf-spectacular(+sidecar), google-auth, requests | BSD / MIT / Apache-2.0 | бэкенд, документация API |
| psycopg | LGPL-3.0 (используется как библиотека) | драйвер PostgreSQL |
| Bootstrap 5.3 | MIT | интерфейс (`web/static/web/vendor/bootstrap`) |
| Tailwind CSS 3 | MIT | только при сборке CSS (результат — `tailwind.css`) |
| Шрифты Manrope, Literata (через Fontsource) | SIL Open Font License 1.1 | интерфейс (`web/static/web/fonts`) |
| Swagger UI, ReDoc (через drf-spectacular-sidecar) | Apache-2.0 / MIT | страницы `/api/docs/`, `/api/redoc/` |

Демонстрационные книги в `seed` — реальные произведения; обложки не поставляются (используйте только изображения с разрешённой лицензией).
