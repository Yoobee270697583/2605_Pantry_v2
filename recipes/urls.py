from django.urls import path
from . import views

# app_name lets base.html highlight the Recipes nav link on these pages
app_name = "recipes"

urlpatterns = [
    path("", views.index, name="index"),
]
