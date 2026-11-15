from django.urls import path

from . import views

# app_name makes these "pantry:index", "pantry:add" etc, and is what
# base.html uses to highlight My Pantry in the nav
app_name = "pantry"

urlpatterns = [
    path("", views.index, name="index"),
    path("add/<int:ingredient_id>/", views.add_item, name="add"),
    path("<int:item_id>/edit/", views.edit_item, name="edit"),
    path("<int:item_id>/delete/", views.delete_item, name="delete"),
]
