from django.db import models
from django.conf import settings
from django.utils import timezone

from households.models import Household
from recipes.models import Recipe

# ============================================================================
# DATABASE MODELS
# ============================================================================
# planned and cooked meals belong to a houehold the same way a pantry does
# so that everyone in the household sees the same planned meanls and the same cooked meals history.
# v1 linked these to a user - v2 only leeps the user as far as to track who did what

class PlannedMeal(models.Model):
    # The recipe the household is planning. Shopping lists will be calculated using these together with the household pantry.
    
    # The household planning the meal - deleting the household would delete is planned meals as well
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="meal_plans"
    )

    # The recipe of the planned meal. CASCADE makes so that deleting a custom recipe also
    # removes it from any planned meals, instead of leaving a planned meal without a recipe
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="meal_plans"
    )

    # Who planned it. SET_NULL so that the planned meal stays if the user account is deleted
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="meal_plans_added"
    )

    # When the meal was planned
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Default oldest first
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.recipe.name} ({self.household})"



class CookedMeal(models.Model):
    # A meal the household has actually cooked. A history log - cooking is what takes the ingredients off the pantry

    # The Household that cooked it - deleting a household deletes its cooked meals history
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="cooked_meals"
    )

    # The recipe that was cooked
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="cooked_meals"
    )

    # Who cooked the meal. SET_NULL so the cooked meals hstory stays if the user account is deleted
    cooked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cooked_meals"
    )

    # When the meal was cooked
    cooked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        # Default most recently cooked first
        ordering = ["-cooked_at"]

    def __str__(self):
        return f"{self.recipe.name} ({self.household})"