from django.utils import timezone

from pantry.models import PantryItem
from recipes.models import Ingredient, Recipe, RecipeIngredient
from recipes.utils import visible_recipes

# works out which recipes a household can make with what's in its pantry

# things nearly every kitchen has, so a recipe never counts them as missing
STAPLES = ["Water", "Salt", "Black Pepper"]


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
