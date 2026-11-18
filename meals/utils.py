from django.utils import timezone

from pantry.models import PantryItem
from suggestions.utils import STAPLES

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
        # PantryItem's Meta ordering already puts the soonest expiry first, no-expiry last
        items = (
            PantryItem.objects.select_for_update()
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
            needed -= used

        name = line.ingredient.name
        # a recipe can list the same ingredient twice, so only report it once
        if needed > 0 and name not in STAPLES and name not in short:
            short.append(name)

    return short