from .dev import *  # noqa: F401,F403

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']  # быстрые тесты
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
CELERY_TASK_ALWAYS_EAGER = True
LOGGING = {'version': 1, 'disable_existing_loggers': True, 'handlers': {'null': {'class': 'logging.NullHandler'}}, 'root': {'handlers': ['null']}}
REST_FRAMEWORK = {**REST_FRAMEWORK, 'DEFAULT_THROTTLE_RATES': {  # noqa: F405
    'anon': '100000/min', 'user': '100000/min', 'password_reset': '1000/hour', 'auth': '10000/hour'}}
