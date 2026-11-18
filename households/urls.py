from django.urls import path

from . import views

app_name = "households"

urlpatterns = [
    path("", views.index, name="index"),
    path("code/", views.new_code, name="new_code"),
    path("join/", views.join, name="join"),
    path("leave/", views.leave, name="leave"),
    path("rename/", views.rename, name="rename"),
    path("members/<int:member_id>/remove/", views.remove, name="remove"),
    path("members/<int:member_id>/make-owner/", views.promote, name="make_owner"),
]
