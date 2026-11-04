from django.urls import path

from . import views as v

urlpatterns = [
    path('notifications/', v.NotificationList.as_view()),
    path('notifications/unread-count/', v.UnreadCount.as_view()),
    path('notifications/read/', v.MarkRead.as_view()),
]
