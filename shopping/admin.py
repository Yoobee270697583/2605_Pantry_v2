from django.contrib import admin

from .models import Order, OrderItem, ShoppingItem


@admin.register(ShoppingItem)
class ShoppingItemAdmin(admin.ModelAdmin):
    list_display = ["ingredient", "quantity", "household", "added_by", "created_at"]
    list_filter = ["household"]
    search_fields = ["ingredient__name"]
    # search box instead of a dropdown with every ingredient in it
    autocomplete_fields = ["ingredient"]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    autocomplete_fields = ["ingredient"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "household", "ordered_by", "ordered_at"]
    list_filter = ["household"]
    # an order's items are shown on the order's own page
    inlines = [OrderItemInline]
