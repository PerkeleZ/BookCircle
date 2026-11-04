from django.urls import path

from . import views as v

urlpatterns = [
    path('reading/', v.ReadingList.as_view()),
    path('reading/<int:book_id>/', v.ReadingDetail.as_view()),
    path('goals/', v.GoalView.as_view()),
    path('goals/<str:period>/', v.GoalDelete.as_view()),
    path('recommendations/', v.Recommendations.as_view()),
]
