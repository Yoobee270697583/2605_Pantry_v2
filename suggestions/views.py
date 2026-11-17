from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from households.utils import get_household
from .utils import get_pantry_ids, get_suggestions

# suggests recipes the household can make (or nearly make) with what's in its pantry

# how many recipe cards to show on each page, the same as My Recipes
RECIPES_PER_PAGE = 24


@login_required
def index(request):
    """The Suggested Recipes page. Shows the recipes the household can make with what's in its pantry right now."""
    household = get_household(request.user)
    pantry_ids = get_pantry_ids(household)
    suggestions = get_suggestions(household, pantry_ids)

    # recipes with nothing missing. the ones that use the most of the pantry come
    # first, then A-Z so the order doesn't jump around between visits
    ready = [suggestion for suggestion in suggestions if not suggestion["missing"]]
    ready.sort(key=lambda suggestion: (-suggestion["using"], suggestion["recipe"].name))

    paginator = Paginator(ready, RECIPES_PER_PAGE)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "suggestions/index.html", {
        "page": page,
        "total": paginator.count,
        # so the page can tell an empty pantry apart from one that just can't make anything yet
        "has_pantry": len(pantry_ids) > 0,
    })
