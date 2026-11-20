from django.urls import path

from . import views

# app_name makes this "shopping:index", and is what base.html uses to
# highlight the Shopping Lists link in the nav
app_name = "shopping"

urlpatterns = [
    path("", views.index, name="index"),
]
