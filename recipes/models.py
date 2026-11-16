from django.conf import settings
from django.db import models

# every ingredient is stored in one of these units, so amounts can always be
# added together and compared against the pantry
UNIT_CHOICES = [
    ("g", "g"),
    ("ml", "mL"),
    ("each", "Each"),
]

# ============================================================================
# DATABASE MODELS
# ============================================================================

class Ingredient(models.Model):
    """The master ingredient list, imported from TheMealDB. Recipes and pantry items both point back here."""

    # ingredient name
    name = models.CharField(max_length=150, unique=True)

    # idIngredient from TheMealDB
    mealdb_id = models.CharField(max_length=50, blank=True)

    # thumbnail image from TheMealDB
    image_url = models.URLField(max_length=500, blank=True)

    # the one unit this ingredient is always measured in (g, ml or each)
    # the recipe import works out which one fits best
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default="each")

    # fdcId from USDA FoodData Central - only filled in for the ingredients
    # we've linked to USDA, empty for everything else
    fdc_id = models.IntegerField(blank=True, null=True)

    # gram weights from USDA, used to convert recipe amounts like "1 cup" or
    # "2 onions" into this ingredient's unit - empty if we don't have them
    grams_per_cup = models.FloatField(blank=True, null=True)
    grams_per_tbsp = models.FloatField(blank=True, null=True)
    grams_per_each = models.FloatField(blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class IngredientAlias(models.Model):
    """Another name for an ingredient, e.g. "Onions" or "Yellow Onion" for Onion, so duplicates from TheMealDB all point at one ingredient."""

    # the other name, spelt the way TheMealDB spells it
    name = models.CharField(max_length=150, unique=True)

    # the ingredient this name really means
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name="aliases"
    )

    class Meta:
        ordering = ["name"]
        # otherwise the admin calls them "ingredient aliass"
        verbose_name_plural = "ingredient aliases"

    def __str__(self):
        return f"{self.name} -> {self.ingredient.name}"


class Recipe(models.Model):
    """A recipe from TheMealDB, or a custom one a household made. TheMealDB recipes are shared by every user, instead of each user getting their own copy like in V1."""

    # idMeal from TheMealDB - empty if the recipe didn't come from there
    mealdb_id = models.CharField(max_length=50, unique=True, blank=True, null=True)

    # recipe name
    name = models.CharField(max_length=150)

    # recipe category e.g. Beef, Dessert
    category = models.CharField(max_length=100, blank=True)

    # recipe's country of origin e.g. Italian
    area = models.CharField(max_length=100, blank=True)

    # recipe instructions
    instructions = models.TextField(blank=True)

    # recipe thumbnail image
    image_url = models.URLField(max_length=500, blank=True)

    # youtube video showing how to cook it, not every recipe has one
    youtube_url = models.URLField(max_length=500, blank=True)

    # where the recipe came from - TheMealDB or Custom
    source = models.CharField(max_length=50, default="TheMealDB")

    # the household that made it - empty for TheMealDB recipes, which everyone can see.
    # a custom recipe is only shown to this household. deleting the household deletes its recipes
    household = models.ForeignKey(
        "households.Household",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="custom_recipes"
    )

    # who in the household made it. SET_NULL so the recipe stays if their account is deleted
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_recipes"
    )

    # date the recipe was added
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RecipeIngredient(models.Model):
    """One ingredient line on a recipe. Tracked lines have a quantity in the ingredient's unit so they can be compared against the pantry."""

    # recipe this line belongs to
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="ingredients"
    )

    # ingredient this line uses - must exist in the Ingredient table
    # PROTECT stops an ingredient being deleted while recipes still use it
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.PROTECT,
        related_name="recipe_ingredients"
    )

    # amount needed, in the ingredient's unit - empty for lines we don't track
    quantity = models.FloatField(blank=True, null=True)

    # false for lines like "pinch" or "to taste" that show on the recipe
    # but don't get taken off the pantry
    is_tracked = models.BooleanField(default=True)

    # the original measure from TheMealDB e.g. "1/2 cup chopped", just for display
    measure_text = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.ingredient.name} ({self.recipe.name})"


class SavedRecipe(models.Model):
    """A recipe a household has saved. Shared by everyone in the household, the same as the pantry."""

    # the household that saved it - everyone in the household sees the same saved list
    household = models.ForeignKey(
        "households.Household",
        on_delete=models.CASCADE,
        related_name="saved_recipes"
    )

    # the recipe that was saved
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="saves"
    )

    # who pressed save. SET_NULL so the recipe stays saved if their account is deleted
    saved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="saved_recipes"
    )

    # when it was saved
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-saved_at"]
        constraints = [
            # a household can only save each recipe once
            models.UniqueConstraint(
                fields=["household", "recipe"],
                name="unique_saved_recipe_per_household",
            ),
        ]

    def __str__(self):
        return f"{self.recipe.name} ({self.household})"
