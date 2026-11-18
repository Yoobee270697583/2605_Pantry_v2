from django.conf import settings
from django.db import models


class SwapTip(models.Model):
    """Claude's swap ideas for a recipe's missing ingredients. Saved so the same question is never paid for twice, and counted for the daily limits."""

    # the household that asked - everyone in the household shares the saved answers
    household = models.ForeignKey(
        "households.Household",
        on_delete=models.CASCADE,
        related_name="swap_tips"
    )

    # the recipe the swaps are for
    recipe = models.ForeignKey(
        "recipes.Recipe",
        on_delete=models.CASCADE,
        related_name="swap_tips"
    )

    # a fingerprint of what was in the pantry and what the recipe was missing when it asked
    # (see get_pantry_key in utils.py). if either changes, so does this, and Claude gets asked again
    pantry_key = models.CharField(max_length=64)

    # Claude's answer, e.g. [{"missing": "Semolina", "swap": "Plain Flour", "tip": "..."}]
    swaps = models.JSONField()

    # who pressed the button. SET_NULL so the answer stays if their account is deleted
    asked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="swap_tips"
    )

    # when Claude was asked - used for the daily limits
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # only one saved answer for each household, recipe and pantry
            models.UniqueConstraint(
                fields=["household", "recipe", "pantry_key"],
                name="unique_swap_tip_per_pantry",
            ),
        ]

    def __str__(self):
        return f"{self.recipe.name} ({self.household})"
