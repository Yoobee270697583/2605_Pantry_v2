from django.urls import path

from . import views

# app_name makes this "suggestions:index", and is what base.html uses to
# highlight Suggested Recipes in the nav
app_name = "suggestions"

urlpatterns = [
    path("", views.index, name="index"),
]
