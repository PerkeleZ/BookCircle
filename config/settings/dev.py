from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ['*']
CORS_ALLOW_ALL_ORIGINS = True
MIDDLEWARE = [m for m in MIDDLEWARE if 'whitenoise' not in m]  # в разработке статику отдаёт runserver
