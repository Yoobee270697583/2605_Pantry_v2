from django.contrib import admin
from .models import Ingredient, Recipe, RecipeIngredient


# shows a recipe's ingredient lines inside that recipe's admin page
class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 0
    # search box instead of a dropdown with every ingredient in it
    autocomplete_fields = ["ingredient"]


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ["name", "unit"]
    list_filter = ["unit"]
    search_fields = ["name"]


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "area", "source"]
    list_filter = ["category", "area", "source"]
    search_fields = ["name"]
    inlines = [RecipeIngredientInline]
