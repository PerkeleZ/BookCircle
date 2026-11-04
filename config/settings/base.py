"""Общие настройки. Всё, что зависит от окружения, берётся из переменных окружения (12-factor)."""
import os
from pathlib import Path

from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(name, default=''):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return env(name, '1' if default else '0').lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    return [x.strip() for x in env(name, default).split(',') if x.strip()]


DEV_SECRET = 'dev-insecure-key-change-me'
SECRET_KEY = env('SECRET_KEY', DEV_SECRET)
DEBUG = False
ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1')
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')

# ---------- Приложения (зависимости идут сверху вниз: common ← accounts ← catalog ← остальные) ----------
INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions',
    'django.contrib.messages', 'django.contrib.staticfiles',
    'rest_framework', 'rest_framework.authtoken', 'corsheaders', 'drf_spectacular', 'drf_spectacular_sidecar',
    # домены продукта
    'common', 'accounts', 'catalog', 'exchange', 'reviews', 'reading', 'meetings', 'notifications',
    # слой композиции (без собственных моделей) и витрина
    'analytics', 'privacy', 'demo', 'web',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'common.middleware.RequestLogMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request', 'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages']},
}]

# ---------- База данных: PostgreSQL при наличии POSTGRES_HOST, иначе SQLite ----------
if env('POSTGRES_HOST'):
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('POSTGRES_DB', 'bookcircle'), 'USER': env('POSTGRES_USER', 'bookcircle'),
        'PASSWORD': env('POSTGRES_PASSWORD', 'bookcircle'), 'HOST': env('POSTGRES_HOST'), 'PORT': env('POSTGRES_PORT', '5432'),
        'CONN_MAX_AGE': int(env('DB_CONN_MAX_AGE', '60')),  # переиспользование соединений
        'CONN_HEALTH_CHECKS': True,
    }}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': env('SQLITE_PATH', str(BASE_DIR / 'db.sqlite3'))}}

# ---------- Кэш: Redis общий для всех экземпляров (лимиты запросов и кэш чтения работают при масштабировании) ----------
if env('REDIS_URL'):
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': env('REDIS_URL'),
                          'KEY_PREFIX': 'bookcircle'}}
else:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}

AUTH_USER_MODEL = 'accounts.User'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': f'django.contrib.auth.password_validation.{n}'}
    for n in ('UserAttributeSimilarityValidator', 'MinimumLengthValidator', 'CommonPasswordValidator', 'NumericPasswordValidator')]
LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Asia/Bishkek'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ---------- DRF ----------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.TokenAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_PAGINATION_CLASS': 'common.pagination.Pagination',
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle', 'rest_framework.throttling.UserRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {
        'anon': env('THROTTLE_ANON', '240/min'), 'user': env('THROTTLE_USER', '1200/min'),
        'password_reset': '5/hour', 'auth': env('THROTTLE_AUTH', '60/hour'),
    },
    'COERCE_DECIMAL_TO_STRING': False,  # оценки (3,5) отдаются числами
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}
SPECTACULAR_SETTINGS = {
    'TITLE': 'BookCircle API', 'VERSION': '1.0.0', 'SERVE_INCLUDE_SCHEMA': False,
    'DESCRIPTION': 'REST API платформы обмена книгами и книжных клубов. Авторизация: заголовок Authorization: Token <token>.',
    'DISABLE_ERRORS_AND_WARNINGS': True,  # у части «действий» (APIView) тела запросов описаны обобщённо — см. docs/ARCHITECTURE.md
    'SWAGGER_UI_DIST': 'SIDECAR', 'SWAGGER_UI_FAVICON_HREF': 'SIDECAR', 'REDOC_DIST': 'SIDECAR',
}
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env_list('CORS_ALLOWED_ORIGINS')

# ---------- Почта: по умолчанию письма печатаются в терминал; для продакшена задайте SMTP через окружение ----------
EMAIL_BACKEND = env('EMAIL_BACKEND', 'common.mail.TerminalEmailBackend')
EMAIL_HOST = env('EMAIL_HOST')
EMAIL_PORT = int(env('EMAIL_PORT', '587'))
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', 'BookCircle <noreply@bookcircle.local>')

FRONTEND_URL = env('FRONTEND_URL', 'http://127.0.0.1:8000')  # публичный адрес сайта (ссылки в письмах)
PASSWORD_RESET_TIMEOUT = 3600
GOOGLE_CLIENT_ID = env('GOOGLE_CLIENT_ID')
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'  # нужно для окна входа Google
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# ---------- Фоновые задачи (Celery). Без брокера задачи выполняются сразу, в процессе (удобно для разработки) ----------
CELERY_BROKER_URL = env('CELERY_BROKER_URL')
CELERY_TASK_ALWAYS_EAGER = not CELERY_BROKER_URL
CELERY_TASK_IGNORE_RESULT = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {
    'remind-overdue-loans': {'task': 'exchange.tasks.remind_overdue', 'schedule': crontab(hour=9, minute=0)},
}

# ---------- Логи ----------
LOG_JSON = env_bool('LOG_JSON', False)
LOGGING = {
    'version': 1, 'disable_existing_loggers': False,
    'formatters': {'json': {'()': 'common.logs.JsonFormatter'}, 'plain': {'format': '%(asctime)s %(levelname)s %(name)s: %(message)s'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'json' if LOG_JSON else 'plain'}},
    'root': {'handlers': ['console'], 'level': env('LOG_LEVEL', 'INFO')},
}
