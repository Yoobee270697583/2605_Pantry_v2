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

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Recipe(models.Model):
    """A recipe imported from TheMealDB. Shared by every user, instead of each user getting their own copy like in V1."""

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
