from django.urls import path

from . import views as v

urlpatterns = [
    path('books/', v.BookList.as_view()),
    path('books/options/', v.BookOptions.as_view()),
    path('books/<int:pk>/', v.BookDetail.as_view()),
    path('books/<int:pk>/hide/', v.BookVisibility.as_view(), {'hide': True}),
    path('books/<int:pk>/unhide/', v.BookVisibility.as_view(), {'hide': False}),
    path('books/<int:pk>/edits/', v.BookEditCreate.as_view()),
    path('genres/', v.GenreList.as_view()),
    path('submissions/', v.Submissions.as_view()),
    path('moderation/books/', v.ModerationBooks.as_view()),
    path('moderation/books/<int:pk>/approve/', v.ModerationBookAction.as_view(), {'approve': True}),
    path('moderation/books/<int:pk>/reject/', v.ModerationBookAction.as_view(), {'approve': False}),
    path('moderation/edits/', v.ModerationEdits.as_view()),
    path('moderation/edits/<int:pk>/approve/', v.ModerationEditAction.as_view(), {'approve': True}),
    path('moderation/edits/<int:pk>/reject/', v.ModerationEditAction.as_view(), {'approve': False}),
]
