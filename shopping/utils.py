import math
from collections import defaultdict

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from households.models import Household
from meals.utils import visible_plans
from pantry.models import PantryItem
from recipes.models import RecipeIngredient
from suggestions.utils import STAPLES
from .forms import AmountForm
from .models import Order, OrderItem, ShoppingItem

# works out a household's shopping list from its planned meals and its pantry, and adds
# what's been bought to the pantry (further down).
# the list itself is never saved - it's worked out again every time the page is opened, so it's
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


# ============================================================================
# ADDING THE LIST TO THE PANTRY
# ============================================================================

class ShoppingError(Exception):
    """An amount someone typed that isn't allowed. The message is shown on the page."""


def add_list_to_pantry(household, user, posted, only_row=None):
    """Adds things on the shopping list to the pantry, using the amounts typed on the page.

    posted is the page's form: one amount for each row, named planned_<ingredient id> for the
    planned meals part and own_<ingredient id> for the household's own items. A row whose
    box is empty is left on the list.

    only_row is for a row's own Add to pantry button - just that row is added ("planned_12")
    and no order is made, like V1's Add to Pantry. Without it every row is added and it's
    saved as an Order, like V1's checkout.

    Returns the names of the ingredients that were added, A to Z - an empty list if nothing was.
    Raises ShoppingError if an amount isn't right, and then nothing is added at all.
    """
    # atomic = the pantry, the order and the own items all change together or not at all
    with transaction.atomic():
        # one of these at a time for each household. if two people press the button at the same
        # moment (or one person double clicks), the second waits here, then finds the first has
        # already taken those rows off the list - so nothing is added twice.
        # no_key=True is a lighter lock: it doesn't hold up things that only point at the
        # household, like someone planning a meal
        Household.objects.select_for_update(no_key=True).get(pk=household.pk)

        # every row that's on the list right now, worked out again here instead of trusting the
        # page - it could be a few minutes old. (the row's name in the form, its ingredient, its own item)
        rows = []
        for item in get_shopping_list(household):
            rows.append((f"planned_{item['ingredient'].id}", item["ingredient"], None))

        # locked so nobody can add onto an own item while it's being bought and taken off the list.
        # of=("self",) locks only the shopping rows, not the Ingredient rows every household shares
        own_items = (
            ShoppingItem.objects.select_for_update(of=("self",))
            .filter(household=household)
            .select_related("ingredient")
        )
        for own_item in own_items:
            rows.append((f"own_{own_item.ingredient_id}", own_item.ingredient, own_item))

        # how much of each ingredient to add. the same ingredient can be in both parts of the
        # list (milk for a planned meal, and milk someone added), so they're added together
        amounts = defaultdict(float)
        ingredients = {}
        bought_own_items = []
        for name, ingredient, own_item in rows:
            if only_row is not None and name != only_row:
                continue

            typed = posted.get(name, "").strip()
            if not typed:
                if only_row is not None:
                    raise ShoppingError(f"Enter an amount for {ingredient.name}.")
                # an empty box at checkout means "didn't buy this one" - it stays on the list
                continue

            form = AmountForm({"quantity": typed})
            if not form.is_valid():
                raise ShoppingError(f"{ingredient.name}: {form.errors['quantity'][0]}")

            quantity = form.cleaned_data["quantity"]
            if ingredient.unit == "each":
                # things that are counted go up to a whole one, like everywhere else on the list
                quantity = math.ceil(quantity)

            amounts[ingredient.id] += quantity
            ingredients[ingredient.id] = ingredient
            if own_item:
                bought_own_items.append(own_item)

        if not amounts:
            return []

        for ingredient_id, quantity in amounts.items():
            quantity = round(quantity, 2)

            # shopping has no expiry date, so it goes onto the pantry item for this ingredient
            # that has no date either, if there is one (the oldest if there are a few). items with
            # a date are a different batch, so they're left alone - the same idea as joining a household.
            # select_for_update because Mark as cooked could be taking some off the same item right now
            item = (
                PantryItem.objects.select_for_update()
                .filter(household=household, ingredient_id=ingredient_id, expiry_date__isnull=True)
                .order_by("id")
                .first()
            )
            if item:
                item.quantity = round(item.quantity + quantity, 2)
                # updated_at has to be listed too, or auto_now doesn't save it
                item.save(update_fields=["quantity", "updated_at"])
            else:
                PantryItem.objects.create(household=household, ingredient_id=ingredient_id, quantity=quantity, added_by=user)

        # own items that were bought come off the list. the planned meals part needs nothing
        # doing - it's worked out from the pantry, which now has more in it
        for own_item in bought_own_items:
            own_item.delete()

        if only_row is None:
            order = Order.objects.create(household=household, ordered_by=user)
            for ingredient_id, quantity in amounts.items():
                OrderItem.objects.create(
                    order=order,
                    ingredient_id=ingredient_id,
                    quantity=round(quantity, 2),
                    # saved with the order - see OrderItem in models.py
                    unit=ingredients[ingredient_id].unit,
                )

        return sorted((ingredient.name for ingredient in ingredients.values()), key=str.lower)
