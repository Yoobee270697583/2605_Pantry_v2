from django.urls import path

from . import views

# Cooked Meals gets its own url file and app_name, the same as planned_urls.py -
# base.html uses the app_name to highlight the right nav link
app_name = "cooked"

urlpatterns = [
    path("", views.cooked_index, name="index"),
]
