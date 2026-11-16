from django.db.models import Q

from .models import Recipe


def visible_recipes(household):
    """Returns every recipe this household is allowed to see - all the TheMealDB ones, plus its own custom ones.

    Every page that lists or opens recipes (and later the pantry suggestions)
    should start from this instead of Recipe.objects.all(), so one household's
    custom recipes never show up for another household.
    """
    # household is empty for TheMealDB recipes, so everyone can see those
    return Recipe.objects.filter(Q(household__isnull=True) | Q(household=household))
