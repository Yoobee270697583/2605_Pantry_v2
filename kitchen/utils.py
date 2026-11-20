from collections import defaultdict
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from pantry.models import PantryItem
from recipes.models import RecipeIngredient
from suggestions.utils import MAX_MISSING, STAPLES, get_pantry_ids, get_suggestions

# what My Kitchen shows: food that's about to expire, and 3 meals to make with what's in the pantry.
# the meal ideas reuse the Suggested Recipes code (suggestions/utils.py), so both pages always agree

# "expiring soon" = within this many days
EXPIRING_DAYS = 7

# how many expiring items the card lists before "and N more"
EXPIRING_SHOWN = 6

# meal ideas shown at a time - "Other ideas" swaps in the next 3
IDEAS_SHOWN = 3


def get_expiring(household):
    """In-date pantry items that expire within EXPIRING_DAYS, soonest first. Run-out (0) items don't count."""
    today = timezone.localdate()
    return (
        PantryItem.objects.filter(
            household=household,
            quantity__gt=0,
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=EXPIRING_DAYS),
        )
        .select_related("ingredient")
        .order_by("expiry_date", "ingredient__name")
    )


def days_left(expiry_date):
    """0 = today, 1 = tomorrow..."""
    return (expiry_date - timezone.localdate()).days


def _low_on(recipe_ids, pantry_amounts):
    """recipe id -> the ingredients the pantry has, but not enough of, for that recipe:
    [{"ingredient": ..., "need": 400, "have": 150}]. Lines with no amount ("to taste") and staples are skipped."""
    needed = defaultdict(lambda: defaultdict(float))
    ingredients = {}
    lines = (
        RecipeIngredient.objects.filter(recipe_id__in=recipe_ids, is_tracked=True, quantity__gt=0)
        .exclude(ingredient__name__in=STAPLES)
        .select_related("ingredient")
    )
    for line in lines:
        # a recipe can list one ingredient twice (e.g. butter for the sauce and the topping), so add them up
        needed[line.recipe_id][line.ingredient_id] += line.quantity
        ingredients[line.ingredient_id] = line.ingredient

    low = {}
    for recipe_id, amounts in needed.items():
        short = []
        for ingredient_id, need in amounts.items():
            # both are floats that have been added up, and that can be a tiny bit out - 0.1 + 0.2 is
            # 0.30000000000000004. round them first, the same as Mark as cooked does (meals/utils.py),
            # or you can be "low on" something when you have exactly enough: need 0.3, have 0.3
            need = round(need, 2)
            have = round(pantry_amounts.get(ingredient_id, 0), 2)
            if have < need:
                short.append({"ingredient": ingredients[ingredient_id], "need": need, "have": have})
        short.sort(key=lambda item: item["ingredient"].name)
        low[recipe_id] = short
    return low


def get_meal_ideas(household):
    """Every recipe worth suggesting today, best first:

    1. recipes with every ingredient in the pantry - enough of everything first, then ones
       you're low on something for (still shown, with what you're low on)
    2. then "almost there" recipes (1 or 2 ingredients missing), to fill the gaps

    Within each group, recipes that use food expiring soon come first, then the ones that
    use the most of the pantry.
    """
    pantry_ids = get_pantry_ids(household)
    if not pantry_ids:
        return []

    suggestions = get_suggestions(household, pantry_ids)

    expiring = {}
    for item in get_expiring(household):
        # keep the soonest date for each ingredient
        expiring.setdefault(item.ingredient_id, item)

    # how much of each ingredient the household has in date - the same stock suggestions use
    today = timezone.localdate()
    pantry_amounts = dict(
        PantryItem.objects.filter(household=household, quantity__gt=0)
        .exclude(expiry_date__lt=today)
        .order_by()  # no default ordering, so each ingredient is one group
        .values_list("ingredient_id")
        .annotate(total=Sum("quantity"))
    )

    makeable = [s for s in suggestions if not s["missing"]]
    almost = [s for s in suggestions if 0 < len(s["missing"]) <= MAX_MISSING]
    low = _low_on([s["recipe"].pk for s in makeable], pantry_amounts)

    # which of each recipe's ingredients are expiring soon
    recipe_ingredients = defaultdict(set)
    for recipe_id, ingredient_id in RecipeIngredient.objects.filter(
        recipe_id__in=[s["recipe"].pk for s in makeable + almost]
    ).values_list("recipe_id", "ingredient_id"):
        recipe_ingredients[recipe_id].add(ingredient_id)

    ideas = []
    for suggestion in makeable + almost:
        recipe = suggestion["recipe"]
        uses_expiring = sorted(
            (expiring[ingredient_id] for ingredient_id in recipe_ingredients[recipe.pk] if ingredient_id in expiring),
            key=lambda item: item.expiry_date,
        )
        ideas.append({
            "recipe": recipe,
            "using": suggestion["using"],
            "missing": suggestion["missing"],
            "low_on": low.get(recipe.pk, []),
            "uses_expiring": uses_expiring,
            "soonest": days_left(uses_expiring[0].expiry_date) if uses_expiring else None,
        })

    def best_first(idea):
        return (
            len(idea["missing"]) > 0,          # makeable before almost there
            len(idea["missing"]),              # 1 missing before 2
            len(idea["low_on"]) > 0,           # enough of everything before low on something
            not idea["uses_expiring"],         # uses expiring food before not
            idea["soonest"] if idea["soonest"] is not None else 99,  # the sooner it expires, the sooner it's used
            -idea["using"],                    # uses more of the pantry
            idea["recipe"].name,
        )

    ideas.sort(key=best_first)
    return ideas


def pick_ideas(ideas, turn):
    """IDEAS_SHOWN ideas for this turn of "Other ideas". Turn 0 is the best 3, turn 1 the next 3,
    and after the last one it starts again from the top - so it's always 3 cards, never a long list."""
    if len(ideas) <= IDEAS_SHOWN:
        return ideas
    pages = -(-len(ideas) // IDEAS_SHOWN)  # rounded up
    start = (turn % pages) * IDEAS_SHOWN
    picked = ideas[start:start + IDEAS_SHOWN]
    # the last turn may be short - top it up from the start so there are always 3
    if len(picked) < IDEAS_SHOWN:
        picked += ideas[:IDEAS_SHOWN - len(picked)]
    return picked
