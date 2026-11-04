from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

api = [  # каждое приложение отвечает за свой кусок API
    path('', include('accounts.urls')),
    path('', include('catalog.urls')),
    path('', include('exchange.urls')),
    path('', include('reviews.urls')),
    path('', include('reading.urls')),
    path('', include('meetings.urls')),
    path('', include('notifications.urls')),
    path('', include('analytics.urls')),
    path('', include('privacy.urls')),
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='docs'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(api)),
    path('', include('common.urls')),
    path('', include('web.urls')),  # витрина (SPA и юридические страницы) — последней
]
