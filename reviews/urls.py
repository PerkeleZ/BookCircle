from django.urls import path

from . import views as v

urlpatterns = [
    path('books/<int:pk>/reviews/', v.BookReviews.as_view()),
    path('books/<int:pk>/review/', v.ReviewPut.as_view()),
    path('reviews/', v.ModerationReviews.as_view()),
    path('reviews/<int:pk>/', v.ModerationReviewDetail.as_view()),
]
