from django.urls import path

from . import views as v

urlpatterns = [
    path('privacy/export/', v.ExportData.as_view()),
    path('privacy/erase/', v.EraseAccount.as_view()),
]
