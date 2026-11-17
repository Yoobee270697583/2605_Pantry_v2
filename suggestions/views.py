import random

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from households.utils import get_household
from recipes.models import SavedRecipe
from .utils import MAX_MISSING, get_pantry_ids, get_suggestions

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
