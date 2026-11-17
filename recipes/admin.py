from django.contrib import admin
from .models import Ingredient, IngredientAlias, Recipe, RecipeIngredient, SavedRecipe


# shows a recipe's ingredient lines inside that recipe's admin page
class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 0
    # search box instead of a dropdown with every ingredient in it
    autocomplete_fields = ["ingredient"]


# shows an ingredient's other names inside that ingredient's admin page
class IngredientAliasInline(admin.TabularInline):
    model = IngredientAlias
    extra = 0


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ["name", "unit"]
    list_filter = ["unit"]
    # aliases__name means searching "yellow onion" still finds Onion
    search_fields = ["name", "aliases__name"]
    inlines = [IngredientAliasInline]


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    # household is empty for TheMealDB recipes
    list_display = ["name", "category", "area", "source", "household"]
    list_filter = ["category", "area", "source"]
    search_fields = ["name"]
    inlines = [RecipeIngredientInline]


@admin.register(SavedRecipe)
class SavedRecipeAdmin(admin.ModelAdmin):
    list_display = ["recipe", "household", "saved_by", "saved_at"]
    search_fields = ["recipe__name", "household__name"]
