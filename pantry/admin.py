from django.contrib import admin

from .models import PantryItem


@admin.register(PantryItem)
class PantryItemAdmin(admin.ModelAdmin):
    list_display = ["ingredient", "quantity", "ingredient_category", "expiry_date", "household", "added_by"]
    list_filter = ["ingredient__category", "household"]
    search_fields = ["ingredient__name"]
    # search box instead of a dropdown with every ingredient in it
    autocomplete_fields = ["ingredient"]

    # the category belongs to the ingredient this can be changed on the Ingredient's admin page
    @admin.display(description="Category", ordering="ingredient__category")
    def ingredient_category(self, item):
        return item.ingredient.get_category_display()
