from .models import Ingredient, IngredientAlias, Recipe


def visible_recipes(household):
    """Returns every recipe this household is allowed to see.

    For now that's every recipe - all the TheMealDB ones and every household's
    custom ones, the same as V1. Every page that lists or opens recipes (and
    later the pantry suggestions) should still start from this instead of
    Recipe.objects.all(), so the privacy toggle (planned as a minor feature)
    only has to change this one function.
    """
    # household isn't used yet - the privacy toggle will need it so a
    # household can still see its own private recipes
    return Recipe.objects.all()


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
