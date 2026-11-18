from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from households.utils import get_household
from .utils import EXPIRING_DAYS, EXPIRING_SHOWN, IDEAS_SHOWN, days_left, get_expiring, get_meal_ideas, pick_ideas


@login_required
def index(request):
    """My Kitchen home page: the household card, food expiring soon, and 3 meals to make today."""
    household = get_household(request.user)

    expiring = list(get_expiring(household))
    for item in expiring:
        item.days_left = days_left(item.expiry_date)

    # ?ideas=1, 2... is which set of 3 "Other ideas" is on - a link, so the back button works
    try:
        turn = max(int(request.GET.get("ideas", 0)), 0)
    except ValueError:
        turn = 0
    ideas = get_meal_ideas(household)

    # the "Other ideas" button asks for just the next 3 cards, so the rest of the page isn't reloaded
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "kitchen/_ideas.html", {
            "ideas": pick_ideas(ideas, turn),
            "has_pantry": True,
        })

    return render(request, "kitchen/index.html", {
        "expiring": expiring[:EXPIRING_SHOWN],
        "more_expiring": max(len(expiring) - EXPIRING_SHOWN, 0),
        "expiring_days": EXPIRING_DAYS,
        "ideas": pick_ideas(ideas, turn),
        "can_rotate": len(ideas) > IDEAS_SHOWN,
        "next_turn": turn + 1,
        "has_pantry": household.pantry_items.filter(quantity__gt=0).exists(),
    })
