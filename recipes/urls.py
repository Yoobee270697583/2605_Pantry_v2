from django.urls import path
from . import views

# app_name lets base.html highlight the Recipes nav link on these pages
app_name = "recipes"

urlpatterns = [
    path("", views.index, name="index"),
    path("create/", views.create_recipe, name="create"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/save/", views.save_recipe, name="save"),
    path("<int:pk>/unsave/", views.unsave_recipe, name="unsave"),
    path("<int:pk>/edit/", views.edit_recipe, name="edit"),
    path("<int:pk>/delete/", views.delete_recipe, name="delete"),
]
