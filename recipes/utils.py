from django.db.models import Q

from .models import Ingredient, IngredientAlias, Recipe


def visible_recipes(household):
    """Returns every recipe this household is allowed to see.

    That's all the TheMealDB ones, other households' custom ones unless
    they're private, and all of this household's own. Every page that lists
    or opens recipes starts from this instead of Recipe.objects.all() (My
    Recipes, the recipe page, saving, Suggested Recipes and the AI swaps),
    so a private recipe can't show up anywhere for another household.
    """
    # not private, or ours. Q is needed for an "or" - filter() on its own only does "and"
    return Recipe.objects.filter(Q(is_private=False) | Q(household=household))


def find_ingredient(name):
    """Finds an ingredient by its name, or by another name for it like "Onions". Upper/lower case doesn't matter.

    Returns None if we don't have it.
    """
    ingredient = Ingredient.objects.filter(name__iexact=name).first()

    # names that merge_ingredients merged into another ingredient, e.g. "onions" -> Onion
    if ingredient is None:
        alias = IngredientAlias.objects.select_related("ingredient").filter(name__iexact=name).first()
        if alias:
            ingredient = alias.ingredient

    return ingredient
