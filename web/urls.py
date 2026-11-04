from django.urls import path

from . import views

urlpatterns = [
    path('', views.Index.as_view()),
    path('legal/<slug:page>/', views.Legal.as_view()),
]
