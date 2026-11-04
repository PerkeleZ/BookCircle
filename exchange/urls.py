from django.urls import path

from . import views as v

urlpatterns = [
    path('books/<int:pk>/copies/', v.BookCopies.as_view()),
    path('copies/', v.CopyList.as_view()),
    path('copies/<int:pk>/', v.CopyDetail.as_view()),
    path('copies/<int:pk>/loans/', v.LoanCreate.as_view()),
    path('loans/', v.LoanList.as_view()),
    path('loans/<int:pk>/<str:action>/', v.LoanAction.as_view()),
    path('alerts/', v.Alerts.as_view()),
]
