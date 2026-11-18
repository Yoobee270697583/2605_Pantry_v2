from django.contrib import admin

from .models import CookedMeal, PlannedMeal


@admin.register(PlannedMeal)
class PlannedMealAdmin(admin.ModelAdmin):
    list_display = ["recipe", "household", "added_by", "created_at"]
    list_filter = ["household"]
    search_fields = ["recipe__name"]
    # search box instead of a dropdown with every recipe in it
    autocomplete_fields = ["recipe"]


@admin.register(CookedMeal)
class CookedMealAdmin(admin.ModelAdmin):
    list_display = ["recipe", "household", "cooked_by", "cooked_at"]
    list_filter = ["household"]
    search_fields = ["recipe__name"]
    autocomplete_fields = ["recipe"]