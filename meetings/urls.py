from django.urls import path

from . import views as v

urlpatterns = [
    path('meetings/', v.MeetingList.as_view()),
    path('meetings/<int:pk>/', v.MeetingDetail.as_view()),
    path('meetings/<int:pk>/join/', v.MeetingJoin.as_view()),
    path('meetings/<int:pk>/leave/', v.MeetingLeave.as_view()),
    path('meetings/<int:pk>/cancel/', v.MeetingCancel.as_view()),
]
