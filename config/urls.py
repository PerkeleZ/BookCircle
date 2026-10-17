from django.conf import settings
from django.contrib import admin
from django.http import FileResponse
from django.urls import include, path


def index(request):  # отдаёт SPA-фронтенд на главной странице
    return FileResponse(open(settings.BASE_DIR / 'frontend' / 'index.html', 'rb'), content_type='text/html; charset=utf-8')


urlpatterns = [
    path('', index),
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
]
