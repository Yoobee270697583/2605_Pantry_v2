from django.urls import path

from . import views

# Previous Orders gets its own url file and app_name, the same as the meals app does for
# Cooked Meals - base.html uses the app_name to highlight the right nav link
app_name = "orders"

urlpatterns = [
    path("", views.orders_index, name="index"),
    path("<int:order_id>/", views.order_detail, name="detail"),
]
