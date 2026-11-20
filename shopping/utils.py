import math
from collections import defaultdict

from django.db.models import Sum
from django.utils import timezone

from meals.utils import visible_plans
from pantry.models import PantryItem
from recipes.models import RecipeIngredient
from suggestions.utils import STAPLES

# works out a household's shopping list from its planned meals and its pantry.
# nothing here is saved - it's worked out again every time the page is opened, so the list is
# already right after a meal is planned, removed or cooked, or the pantry changes.
# V1 saved the list and had to call sync_shopping_list() from every one of those places


def get_shopping_list(household):
    """What the household needs to buy for its planned meals, A to Z.

    For every ingredient the planned meals use, it's what they need all together minus what's
    in the pantry. Anything the pantry already has enough of is left out, and staples like
    Salt are never on the list (the same as Suggested Recipes).

    Returns a list of dicts, one for each thing to buy:
        ingredient - the Ingredient
        need       - how much the planned meals need, or None if no recipe gives an amount ("to taste")
        have       - how much is in the pantry
        to_buy     - need minus have, or None if need is None
        meals      - the names of the planned meals that use it
    """
    # a recipe that's planned twice needs twice as much, so count how many times each one is planned.
    # visible_plans leaves out plans for recipes another household has since made private
    times_planned = defaultdict(int)
    for recipe_id in visible_plans(household).values_list("recipe_id", flat=True):
        times_planned[recipe_id] += 1

    if not times_planned:
        return []

    lines = (
        RecipeIngredient.objects.filter(recipe_id__in=times_planned.keys())
        .exclude(ingredient__name__in=STAPLES)
        .select_related("ingredient", "recipe")
    )

    needed = defaultdict(float)
    ingredients = {}
    meals = defaultdict(set)
    for line in lines:
        times = times_planned[line.recipe_id]
        ingredients[line.ingredient_id] = line.ingredient
        meals[line.ingredient_id].add(line.recipe.name if times == 1 else f"{line.recipe.name} x{times}")

        # lines with no amount ("to taste", "a pinch") have nothing to add up.
        # a recipe can list one ingredient twice (butter for the sauce and the topping), so += adds them
        if line.is_tracked and line.quantity:
            needed[line.ingredient_id] += line.quantity * times

    # what's in the pantry. run-out (0) and expired items don't count as stock - the same
    # rule Suggested Recipes, My Kitchen and Mark as cooked use
    today = timezone.localdate()
    in_pantry = dict(
        PantryItem.objects.filter(household=household, ingredient_id__in=ingredients.keys(), quantity__gt=0)
        .exclude(expiry_date__lt=today)
        .order_by()  # no default ordering, so each ingredient is one group
        .values_list("ingredient_id")
        .annotate(total=Sum("quantity"))
    )

    shopping_list = []
    for ingredient_id, ingredient in ingredients.items():
        # amounts are floats that have been added up, which can be a tiny bit out
        # (0.1 + 0.2 is 0.30000000000000004), so they're rounded the same as Mark as cooked does
        have = round(in_pantry.get(ingredient_id, 0), 2)

        if ingredient_id in needed:
            need = round(needed[ingredient_id], 2)
            to_buy = round(need - have, 2)
            if to_buy <= 0:
                # the pantry already has enough
                continue
            if ingredient.unit == "each":
                # you can't buy half an onion, so things that are counted go up to a whole one
                to_buy = math.ceil(to_buy)
        else:
            # no recipe says how much, so there's no amount to work out.
            # it's only on the list if the pantry has none of it at all
            if have > 0:
                continue
            need = None
            to_buy = None

        shopping_list.append({
            "ingredient": ingredient,
            "need": need,
            "have": have,
            "to_buy": to_buy,
            "meals": sorted(meals[ingredient_id]),
        })

    shopping_list.sort(key=lambda item: item["ingredient"].name.lower())
    return shopping_list
