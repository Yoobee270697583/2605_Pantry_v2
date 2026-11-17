from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from households.utils import get_household
from .utils import MAX_MISSING, get_pantry_ids, get_suggestions

# suggests recipes the household can make (or nearly make) with what's in its pantry

# how many recipe cards to show on each page, the same as My Recipes
RECIPES_PER_PAGE = 24


@login_required
def index(request):
    """The Suggested Recipes page. Has two tabs: recipes the household can make with what's in its
    pantry right now, and recipes it's only 1 or 2 ingredients away from."""
    active_tab = request.GET.get("tab", "ready")
    # anything else, like a typo in the url, just shows the ready tab
    if active_tab not in ["ready", "almost"]:
        active_tab = "ready"

    household = get_household(request.user)
    pantry_ids = get_pantry_ids(household)
    suggestions = get_suggestions(household, pantry_ids)

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

    paginator = Paginator(shown, RECIPES_PER_PAGE)
    page = paginator.get_page(request.GET.get("page"))

    # the current tab without the page number, so the previous/next links stay on the same tab
    params = request.GET.copy()
    params.pop("page", None)

    return render(request, "suggestions/index.html", {
        "active_tab": active_tab,
        "page": page,
        "total": paginator.count,
        # for the numbers on the tabs
        "ready_count": len(ready),
        "almost_count": len(almost),
        # so the page can tell an empty pantry apart from one that just can't make anything yet
        "has_pantry": len(pantry_ids) > 0,
        "filter_params": params.urlencode(),
    })
