from django.urls import path

from . import views

# app_name lets templates use {% url 'accounts:settings' %}.
# allauth's own pages (login, password change) are under /accounts/ in config/urls.py
app_name = "accounts"

urlpatterns = [
    path("", views.settings_page, name="settings"),
    path("google/disconnect/", views.disconnect_google, name="disconnect_google"),
]
