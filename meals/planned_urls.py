from django.urls import path

from . import views

# the meals app has two url files so Planned Meals and Cooked Meals each get
# their own app_name - base.html uses it to highlight the right nav link
app_name = "planned"

urlpatterns = [
    path("", views.planned_index, name="index"),
    path("add/<int:recipe_id>/", views.add_to_plan, name="add"),
    path("<int:plan_id>/remove/", views.remove_from_plan, name="remove"),
    path("<int:plan_id>/cook/", views.mark_as_cooked, name="cook"),
]