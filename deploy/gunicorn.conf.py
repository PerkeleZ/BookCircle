"""Настройки gunicorn. Всё переопределяется переменными окружения — без пересборки образа."""
import multiprocessing
import os

bind = '0.0.0.0:8000'
workers = int(os.environ.get('WEB_CONCURRENCY', min(4, multiprocessing.cpu_count() * 2 + 1)))
threads = int(os.environ.get('GUNICORN_THREADS', 4))
worker_class = 'gthread'  # потоки внутри процесса: запросы к БД не блокируют соседние
timeout = 30
graceful_timeout = 30
keepalive = 5
max_requests = 2000  # плавный перезапуск воркеров защищает от утечек памяти
max_requests_jitter = 200
accesslog = None  # запросы логирует приложение (JSON, с X-Request-ID)
errorlog = '-'
loglevel = os.environ.get('LOG_LEVEL', 'info').lower()
forwarded_allow_ips = '*'  # работаем за nginx/ingress
worker_tmp_dir = '/dev/shm'
