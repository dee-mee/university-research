from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from .views import RegisterView, PasswordResetView, login_view, user_dashboard
from django.contrib.auth.decorators import login_required
from django.shortcuts import render



# Dashboard views
urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', login_view, name='login'),
    path('password-reset/', PasswordResetView.as_view(), name='password_reset'),
    path('user/dashboard/', user_dashboard, name='user_dashboard'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
