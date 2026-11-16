from django.db.models import Q

from .models import Ingredient, IngredientAlias, Recipe


def visible_recipes(household):
    """Returns every recipe this household is allowed to see - all the TheMealDB ones, plus its own custom ones.

    Every page that lists or opens recipes (and later the pantry suggestions)
    should start from this instead of Recipe.objects.all(), so one household's
    custom recipes never show up for another household.
    """
    # household is empty for TheMealDB recipes, so everyone can see those
    return Recipe.objects.filter(Q(household__isnull=True) | Q(household=household))


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
