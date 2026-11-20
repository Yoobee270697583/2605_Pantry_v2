from django.urls import path

from . import views

# app_name makes these "shopping:index", "shopping:add" etc, and is what base.html
# uses to highlight the Shopping Lists link in the nav
app_name = "shopping"

urlpatterns = [
    path("", views.index, name="index"),
    path("add/<int:ingredient_id>/", views.add_item, name="add"),
    path("<int:item_id>/remove/", views.remove_item, name="remove"),
]
