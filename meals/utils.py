from django.utils import timezone

from pantry.models import PantryItem
from recipes.utils import visible_recipes
from suggestions.utils import STAPLES
from .models import CookedMeal, PlannedMeal


def visible_plans(household):
    """Returns the household's planned meals, leaving out any whose recipe it can't see any more.

    That happens if another household makes its recipe private after this household planned it.
    The plan is hidden, not deleted, so it comes back if the recipe is made public again - the
    same as saved recipes. Planned Meals uses this, and My Kitchen and the shopping list should
    too, so a private recipe can't show up anywhere for another household.
    """
    # visible_recipes leaves out other households' private recipes (see recipes/utils.py)
    return PlannedMeal.objects.filter(household=household, recipe__in=visible_recipes(household))


def visible_cooked(household):
    """Returns the household's cooked meals, leaving out any whose recipe it can't see any more.

    The same rule as visible_plans - if another household makes its recipe private after this
    household cooked it, the meal is hidden from the history, and comes back if it's made public again.
    """
    return CookedMeal.objects.filter(household=household, recipe__in=visible_recipes(household))


# taking a recipe's ingredients off the pantry when it's cooked.
# replaces V1's subtract_recipe_ingredients_from_pantry - recipe lines and
# pantry items are both stored in the ingredient's own unit (g, ml or each),
# so there's no parsing or unit matching, and nothing gets skipped on a unit mismatch


def deduct_recipe_from_pantry(household, recipe):
    """Takes the recipe's tracked ingredients off the household's pantry. Uses the soonest-expiring stock first.

    Must be called inside transaction.atomic() - select_for_update locks the
    pantry rows so two people cooking at the same moment can't both take the same stock.

    Returns the names of ingredients the pantry didn't have enough of, so the
    page can tell the user. Staples like Salt never count as short.
    """
    today = timezone.localdate()
    short = []

    # untracked lines ("pinch", "to taste") have no quantity, so there's nothing to take off
    lines = recipe.ingredients.filter(is_tracked=True, quantity__gt=0).select_related("ingredient")

    for line in lines:
        needed = line.quantity

        # same rule as suggestions: run-out (0) and expired items don't count as stock.
        # PantryItem's Meta ordering already puts the soonest expiry first, no-expiry last.
        # that ordering joins the ingredient table (for ingredient__name), so of=("self",) is needed
        # to lock only this household's pantry rows, not the Ingredient row every household shares
        items = (
            PantryItem.objects.select_for_update(of=("self",))
            .filter(household=household, ingredient=line.ingredient, quantity__gt=0)
            .exclude(expiry_date__lt=today)
        )

        for item in items:
            if needed <= 0:
                break
            # take what we need, or everything in this item if that's not enough
            used = min(item.quantity, needed)
            # round so float maths doesn't leave things like 0.30000000000000004 g.
            # an item that hits 0 stays in the pantry (not deleted like V1) so the shopping list can use it later
            item.quantity = round(item.quantity - used, 2)
            # updated_at has to be listed too, or auto_now doesn't save it
            item.save(update_fields=["quantity", "updated_at"])
            # rounded too - otherwise a recipe needing 1 with 0.7 + 0.3 in the pantry is left
            # needing 0.00000000000000005 and says it's short when there was exactly enough
            needed = round(needed - used, 2)

        name = line.ingredient.name
        # a recipe can list the same ingredient twice, so only report it once
        if needed > 0 and name not in STAPLES and name not in short:
            short.append(name)

    return short