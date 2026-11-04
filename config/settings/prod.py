from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import DEV_SECRET, SECRET_KEY, env, env_bool

DEBUG = False
if SECRET_KEY == DEV_SECRET and not env_bool('ALLOW_INSECURE_KEY'):
    raise ImproperlyConfigured('Задайте SECRET_KEY в окружении (длинная случайная строка).')

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},  # хэши в именах файлов → вечный кэш
}
LOG_JSON = True
LOGGING = {**LOGGING, 'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'json'}}}  # noqa: F405

# за обратным прокси (nginx / ingress / облачный балансировщик)
if env_bool('BEHIND_PROXY', True):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST = True
SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', False)  # включайте, когда TLS завершается на периметре
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = env_bool('SECURE_COOKIES', False)
SECURE_HSTS_SECONDS = int(env('SECURE_HSTS_SECONDS', '0'))
SECURE_CONTENT_TYPE_NOSNIFF = True

if env('SENTRY_DSN'):  # необязательно: pip install sentry-sdk
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=env('SENTRY_DSN'), traces_sample_rate=float(env('SENTRY_TRACES', '0.05')))
    except ImportError:
        pass
