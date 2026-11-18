import random

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from households.utils import get_household
from meals.models import PlannedMeal
from recipes.models import SavedRecipe
from recipes.utils import find_ingredient, visible_recipes
from .utils import MAX_MISSING, get_missing, get_pantry_ids, get_saved_swaps, get_suggestions, get_swap_tips

# suggests recipes the household can make (or nearly make) with what's in its pantry

# how many recipe cards to show on each page, the same as My Recipes
RECIPES_PER_PAGE = 24


@login_required
def index(request):
    """The Suggested Recipes page. Has two tabs: recipes the household can make with what's in its
    pantry right now, and recipes it's only 1 or 2 ingredients away from. Both tabs can be cut down
    to just the household's saved recipes, and "Surprise me" picks one recipe from the tab at random."""
    active_tab = request.GET.get("tab", "ready")
    # anything else, like a typo in the url, just shows the ready tab
    if active_tab not in ["ready", "almost"]:
        active_tab = "ready"

    # ?saved=1 only suggests recipes the household has saved - V1 only ever looked at saved recipes
    saved_only = request.GET.get("saved") == "1"

    household = get_household(request.user)
    pantry_ids = get_pantry_ids(household)
    suggestions = get_suggestions(household, pantry_ids)

    # ids of every recipe this household has saved, for the saved only filter and the "Saved" badge on each card
    saved_ids = set(SavedRecipe.objects.filter(household=household).values_list("recipe_id", flat=True))
    if saved_only:
        suggestions = [suggestion for suggestion in suggestions if suggestion["recipe"].pk in saved_ids]

    # and every recipe it has in Planned Meals, for a "Planned" badge, the same as My Recipes
    planned_ids = set(PlannedMeal.objects.filter(household=household).values_list("recipe_id", flat=True))

    # recipes with nothing missing. the ones that use the most of the pantry come
    # first, then A-Z so the order doesn't jump around between visits
    ready = [suggestion for suggestion in suggestions if not suggestion["missing"]]
    ready.sort(key=lambda suggestion: (-suggestion["using"], suggestion["recipe"].name))

    # recipes only missing 1 or 2 ingredients - V1 only ever suggested recipes you had
    # everything for (V1 defect 1). fewest missing first, then the same order as above
    almost = [suggestion for suggestion in suggestions if 0 < len(suggestion["missing"]) <= MAX_MISSING]
    almost.sort(key=lambda suggestion: (len(suggestion["missing"]), -suggestion["using"], suggestion["recipe"].name))

    if active_tab == "almost":
        shown = almost
    else:
        shown = ready

    # how many recipes are on this tab, before surprise me picks one of them
    total = len(shown)

    # "Surprise me" picks one recipe from the tab at random, like V1's random suggestion
    picked = None
    if request.GET.get("surprise") == "1" and shown:
        # "Pick another" sends the recipe it's showing as ?last=, so the same one doesn't come up twice in a row
        last_id = request.GET.get("last", "")
        choices = [suggestion for suggestion in shown if str(suggestion["recipe"].pk) != last_id]
        # if it's the only recipe on the tab, it has to be that one again
        if not choices:
            choices = shown
        picked = random.choice(choices)
        shown = [picked]

    paginator = Paginator(shown, RECIPES_PER_PAGE)
    page = paginator.get_page(request.GET.get("page"))

    # the current tab and saved filter without the page number or surprise me, so the
    # previous/next, surprise me and show all links keep them
    params = request.GET.copy()
    params.pop("page", None)
    params.pop("surprise", None)
    params.pop("last", None)

    return render(request, "suggestions/index.html", {
        "active_tab": active_tab,
        "saved_only": saved_only,
        "saved_ids": saved_ids,
        "planned_ids": planned_ids,
        # the suggestion surprise me picked, None if it wasn't pressed
        "picked": picked,
        "page": page,
        "total": total,
        # for the numbers on the tabs
        "ready_count": len(ready),
        "almost_count": len(almost),
        # so the page can tell an empty pantry apart from one that just can't make anything yet
        "has_pantry": len(pantry_ids) > 0,
        "filter_params": params.urlencode(),
    })


@login_required
def swaps(request, pk):
    """AI swap ideas for the ingredients a recipe is missing. The GET page shows the saved ideas,
    or a button to ask for them. The button POSTs here to ask Claude, then comes back to the GET."""
    household = get_household(request.user)
    # the same recipes the suggestions come from, so one the household can't see is a 404
    recipe = get_object_or_404(visible_recipes(household), pk=pk)
    pantry_ids = get_pantry_ids(household)
    missing = get_missing(recipe, pantry_ids)

    # only for recipes that are almost there - nothing missing means nothing to swap,
    # and swapping lots of ingredients would really be a different recipe
    can_ask = 0 < len(missing) <= MAX_MISSING

    # a POST and not a link, because asking Claude costs money and links can get opened by anything
    if request.method == "POST":
        if can_ask:
            # the answer gets saved, so the GET page shows it after the redirect
            answer, problem = get_swap_tips(household, request.user, recipe, missing, pantry_ids)
            if problem == "limit":
                messages.warning(request, "You've used all your AI swap tips for now. Try again tomorrow.")
            elif problem == "unavailable":
                messages.error(request, "AI tips aren't available right now. Try again in a minute.")
        # back to the GET page, so refreshing it doesn't ask again
        return redirect("suggestions:swaps", pk=recipe.pk)

    # the answer from last time if the pantry hasn't changed since. None if it hasn't asked yet
    saved_swaps = None
    if can_ask:
        saved_swaps = get_saved_swaps(household, recipe, missing, pantry_ids)

    # check each swap against the pantry, so the page can say which ones you've already got
    swap_list = []
    if saved_swaps:
        for swap in saved_swaps:
            # find_ingredient matches other names too, e.g. "onions" -> Onion
            ingredient = find_ingredient(swap["swap"])
            swap_list.append({
                "missing": swap["missing"],
                "swap": swap["swap"],
                "tip": swap["tip"],
                "in_pantry": ingredient is not None and ingredient.id in pantry_ids,
            })

    return render(request, "suggestions/swaps.html", {
        "recipe": recipe,
        "missing": missing,
        "can_ask": can_ask,
        # True once there's an answer, even if it was "no ideas"
        "asked": saved_swaps is not None,
        "swaps": swap_list,
    })
