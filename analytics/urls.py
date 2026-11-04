from django.urls import path

from . import views as v

urlpatterns = [
    path('stats/', v.StaffStats.as_view()),
    path('stats/public/', v.PublicStats.as_view()),
]
