from django.conf import settings
from django.db import models

from households.models import Household
from recipes.models import Ingredient

# same categories as V1, so the wording stays the same everywhere
CATEGORY_CHOICES = [
    ("fruit_veg", "Fruit & Vegetables"),
    ("meat_seafood", "Meat & Seafood"),
    ("dairy_eggs", "Dairy & Eggs"),
    ("pantry_staples", "Pantry Staples"),
    ("frozen", "Frozen"),
    ("bakery", "Bakery"),
    ("herbs_spices", "Herbs & Spices"),
    ("condiments", "Sauces & Condiments"),
    ("drinks", "Drinks"),
    ("other", "Other"),
]

# ============================================================================
# DATABASE MODELS
# ============================================================================

class PantryItem(models.Model):
    """An ingredient a household currently has in stock. Used for shopping lists, recipe suggestions and deduction."""

    # the household that owns this item - everyone in the household shares it.
    # deleting the household deletes its pantry
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="pantry_items"
    )

    # who added it - kept for the household activity feed (10.3) and for checking
    # accuracy if numbers ever look wrong. SET_NULL so the item stays in the
    # household's pantry if that person's account is deleted
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pantry_items_added"
    )

    # ingredient this refers to - must exist in the Ingredient table
    # PROTECT stops an ingredient being deleted while someone has it in their pantry
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.PROTECT,
        related_name="pantry_items"
    )

    # amount currently owned, always in the ingredient's own unit (g, ml or each)
    # so it lines up with RecipeIngredient.quantity - unlike V1, there's no
    # separate unit field the user can pick
    quantity = models.FloatField()

    # item category e.g. fruit_veg - see CATEGORY_CHOICES
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)

    # optional expiry date
    expiry_date = models.DateField(blank=True, null=True)

    # when the item was added / last changed
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # soonest expiry first, items with no expiry date at the end
        ordering = [models.F("expiry_date").asc(nulls_last=True), "ingredient__name"]

        # data integrity rules enforced by the database itself, so bad data
        # can't get in even if it skips the form (admin, scripts, deduction code)
        constraints = [
            # quantity can reach 0 during deduction but never go negative
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name="pantry_quantity_not_negative",
            ),
            # category must be one of CATEGORY_CHOICES
            models.CheckConstraint(
                condition=models.Q(category__in=[value for value, label in CATEGORY_CHOICES]),
                name="pantry_category_valid",
            ),
        ]

    def __str__(self):
        return f"{self.ingredient.name} ({self.household})"
