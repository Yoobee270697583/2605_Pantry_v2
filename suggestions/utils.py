import hashlib
from datetime import timedelta

from django.utils import timezone

from pantry.models import PantryItem
from recipes.models import Ingredient, Recipe, RecipeIngredient
from recipes.utils import visible_recipes
from .ai_helper import get_swaps
from .models import SwapTip

# works out which recipes a household can make with what's in its pantry,
# and gets the AI swap tips for the ones it's almost there with

# things nearly every kitchen has, so a recipe never counts them as missing
STAPLES = ["Water", "Salt", "Black Pepper"]

# a recipe missing this many ingredients or fewer shows under "Almost there".
# the page says "1 or 2", so change that wording too if this changes
MAX_MISSING = 2

# how many times Claude can be asked for swap tips in 24 hours - by one household, and by
# everyone on the site together - so a bug or someone spamming the button can't use up
# the API credit. saved answers that get reused don't count
HOUSEHOLD_DAILY_LIMIT = 20
SITE_DAILY_LIMIT = 200


def get_pantry_ids(household):
    """Returns the ids of the ingredients the household has right now.

    Items that have run out (quantity 0) or are past their expiry date don't count.
    """
    today = timezone.localdate()
    items = PantryItem.objects.filter(household=household, quantity__gt=0).exclude(expiry_date__lt=today)
    return set(items.values_list("ingredient_id", flat=True))


def get_suggestions(household, pantry_ids):
    """Checks every recipe the household can see against its pantry (pantry_ids from get_pantry_ids).

    Returns one dict for each recipe that uses at least one thing from the pantry:
        recipe  - the Recipe
        using   - how many of its ingredients are in the pantry
        missing - the Ingredients it needs that aren't (staples never count as missing)

    Everything is matched by ingredient id, so merged names (e.g. Onions -> Onion)
    line up, and an ingredient a recipe lists twice only counts once.
    """
    if not pantry_ids:
        return []

    staple_ids = set(Ingredient.objects.filter(name__in=STAPLES).values_list("id", flat=True))

    # recipe id -> the ids of the ingredients it needs. a set, so one listed twice only counts once
    needs = {}
    lines = RecipeIngredient.objects.filter(recipe__in=visible_recipes(household)).values_list("recipe_id", "ingredient_id")
    for recipe_id, ingredient_id in lines:
        if recipe_id not in needs:
            needs[recipe_id] = set()
        needs[recipe_id].add(ingredient_id)

    matches = []
    for recipe_id, ingredient_ids in needs.items():
        using = ingredient_ids & pantry_ids
        # it has to use something from the pantry, otherwise it isn't really a suggestion
        if not using:
            continue
        missing = ingredient_ids - pantry_ids - staple_ids
        matches.append({"recipe_id": recipe_id, "using": len(using), "missing_ids": missing})

    # get all the recipes and missing ingredients in 2 queries, instead of 2 for every recipe
    recipes = Recipe.objects.in_bulk([match["recipe_id"] for match in matches])
    all_missing_ids = set()
    for match in matches:
        all_missing_ids = all_missing_ids | match["missing_ids"]
    ingredients = Ingredient.objects.in_bulk(all_missing_ids)

    suggestions = []
    for match in matches:
        missing = [ingredients[ingredient_id] for ingredient_id in match["missing_ids"]]
        missing.sort(key=lambda ingredient: ingredient.name)
        suggestions.append({
            "recipe": recipes[match["recipe_id"]],
            "using": match["using"],
            "missing": missing,
        })

    return suggestions


def get_pantry_key(pantry_ids, missing):
    """A fingerprint of what's in the pantry and what a recipe is missing, so a saved AI answer
    is only reused while both are still the same."""
    pantry_part = ",".join(str(ingredient_id) for ingredient_id in sorted(pantry_ids))
    missing_part = ",".join(str(ingredient.id) for ingredient in sorted(missing, key=lambda ingredient: ingredient.id))
    # sha256 turns any amount of text into 64 characters, so it always fits in SwapTip.pantry_key
    return hashlib.sha256(f"{pantry_part}|{missing_part}".encode()).hexdigest()


def get_swap_tips(household, user, recipe, missing, pantry_ids):
    """Gets Claude's swap ideas for the ingredients a recipe is missing.

    Reuses the household's saved answer if its pantry hasn't changed since it last asked,
    otherwise asks Claude (if it's under the daily limits) and saves the answer.

    Returns (swaps, problem):
        swaps   - the list of swaps from ai_helper.get_swaps, or None
        problem - None if it worked, "limit" if a daily limit has been hit,
                  or "unavailable" if Claude couldn't be reached
    """
    # nothing missing, so nothing to swap
    if not missing:
        return [], None

    pantry_key = get_pantry_key(pantry_ids, missing)

    # asked before with the same pantry - reuse that answer, it's free and instant
    saved = SwapTip.objects.filter(household=household, recipe=recipe, pantry_key=pantry_key).first()
    if saved:
        return saved.swaps, None

    # the last 24 hours instead of "today", because the server runs on UTC time,
    # so a new day would start around midday in NZ
    since = timezone.now() - timedelta(hours=24)
    asked_recently = SwapTip.objects.filter(created_at__gte=since)
    if asked_recently.filter(household=household).count() >= HOUSEHOLD_DAILY_LIMIT:
        return None, "limit"
    if asked_recently.count() >= SITE_DAILY_LIMIT:
        return None, "limit"

    pantry = Ingredient.objects.filter(id__in=pantry_ids)
    swaps = get_swaps(recipe, missing, pantry)
    if swaps is None:
        return None, "unavailable"

    # get_or_create in case someone else in the household pressed the button at the same time
    SwapTip.objects.get_or_create(
        household=household,
        recipe=recipe,
        pantry_key=pantry_key,
        defaults={"swaps": swaps, "asked_by": user},
    )
    return swaps, None
