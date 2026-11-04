from django.urls import path

from . import views as v

urlpatterns = [
    path('auth/register/', v.RegisterView.as_view()),
    path('auth/login/', v.LoginView.as_view()),
    path('auth/logout/', v.LogoutView.as_view()),
    path('auth/me/', v.MeView.as_view()),
    path('auth/google/config/', v.PublicConfig.as_view()),
    path('auth/password-reset/', v.PasswordResetRequest.as_view()),
    path('auth/password-reset/confirm/', v.PasswordResetConfirm.as_view()),
    path('auth/google/', v.GoogleLogin.as_view()),
    path('auth/google/link/', v.GoogleLink.as_view()),
    path('auth/google/unlink/', v.GoogleUnlink.as_view()),
]
