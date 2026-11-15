from django.contrib import admin

from .models import PantryItem


@admin.register(PantryItem)
class PantryItemAdmin(admin.ModelAdmin):
    list_display = ["ingredient", "quantity", "category", "expiry_date", "household", "added_by"]
    list_filter = ["category", "household"]
    search_fields = ["ingredient__name"]
    # search box instead of a dropdown with every ingredient in it
    autocomplete_fields = ["ingredient"]
