from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from households.utils import get_household
from meals.utils import visible_plans
from .utils import get_shopping_list

# the shopping list - what to buy for the household's planned meals


@login_required
def index(request):
    """The Shopping List page. Shows what the household needs to buy for its planned meals."""
    household = get_household(request.user)

    return render(request, "shopping/index.html", {
        "shopping_list": get_shopping_list(household),
        # how many meals the list is for. also tells "nothing planned" apart from "you have everything"
        "planned_count": visible_plans(household).count(),
    })
