.PHONY: run test seed migrate assets docker docker-scale lint remind

run:            ## сервер разработки: http://127.0.0.1:8000
	python manage.py migrate && python manage.py runserver

seed:           ## демоданные (--reset пересоздаёт)
	python manage.py seed --reset

test:           ## автотесты
	python manage.py test

lint:
	python -m pyflakes . | grep -v "unused\|unable to detect\|may be undefined" || true

assets:         ## пересобрать Tailwind, Bootstrap и шрифты (нужен Node.js, только разработчику)
	cd frontend-src && npm install && npm run build

remind:         ## напоминания о просрочке вручную (то же, что ежедневная задача Celery)
	python manage.py remind_overdue

docker:         ## весь стек: http://localhost:8000
	docker compose up --build

docker-scale:   ## 3 экземпляра веба и 2 воркера
	docker compose up -d --build --scale web=3 --scale worker=2
