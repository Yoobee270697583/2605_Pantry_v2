from django.conf import settings
from django.db import models
from django.utils import timezone

from households.models import Household
from recipes.models import UNIT_CHOICES, Ingredient

# ============================================================================
# DATABASE MODELS
# ============================================================================
# most of the shopping list isn't saved in these tables at all. what the planned meals need
# is worked out from the planned meals and the pantry every time the page is opened
# (shopping/utils.py), so it can never be out of date. V1 saved those rows, and had to
# re-sync them whenever a meal was planned, removed or cooked.
# what is saved here: the things people add to the list themselves, and the orders
# (a shopping list that's been checked out into the pantry)

class ShoppingItem(models.Model):
    """Something a household added to its shopping list by hand, on top of what its planned meals need."""

    # the household whose list it's on - everyone in the household shares one list,
    # the same as the pantry. deleting the household deletes its list
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="shopping_items"
    )

    # what to buy. PROTECT like pantry items - an ingredient can't be deleted while it's on someone's list
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.PROTECT,
        related_name="shopping_items"
    )

    # how much to buy, always in the ingredient's own unit (g, ml or each) like the pantry
    quantity = models.FloatField()

    # who added it. SET_NULL so it stays on the list if that person's account is deleted
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shopping_items_added"
    )

    # when it was added
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ingredient__name"]

        # enforced by the database itself, like the pantry's rules
        constraints = [
            # an amount to buy has to be more than nothing
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="shopping_quantity_above_zero",
            ),
            # one row for each ingredient - adding the same thing again adds onto the row that's there
            models.UniqueConstraint(
                fields=["household", "ingredient"],
                name="shopping_one_row_per_ingredient",
            ),
        ]

    def __str__(self):
        return f"{self.ingredient.name} ({self.household})"


class Order(models.Model):
    """A shopping list that's been checked out into the pantry. Kept as a history, for Previous Orders."""

    # the household that did the shop - deleting the household deletes its orders
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="orders"
    )

    # who checked it out. SET_NULL so the order stays if that person's account is deleted
    ordered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders"
    )

    # when it was checked out
    ordered_at = models.DateTimeField(default=timezone.now)

    class Meta:
        # newest first
        ordering = ["-ordered_at"]

    def __str__(self):
        return f"Order {self.pk} ({self.household})"


class OrderItem(models.Model):
    """One ingredient, and how much of it, that an Order added to the pantry."""

    # the order it was part of - deleting the order deletes its items
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items"
    )

    # what was bought. PROTECT so an old order never ends up with a line that has no ingredient
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.PROTECT,
        related_name="order_items"
    )

    # how much was added to the pantry
    quantity = models.FloatField()

    # the ingredient's unit when the order was made. saved with the order (the pantry and the
    # shopping list just use the ingredient's unit) so an old order still reads right if the
    # ingredient is switched to a different unit later, like salt going from ml to grams
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES)

    class Meta:
        ordering = ["ingredient__name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="order_item_quantity_above_zero",
            ),
        ]

    def __str__(self):
        return f"{self.ingredient.name} (order {self.order_id})"
