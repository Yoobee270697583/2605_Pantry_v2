from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timesince import timesince
from django.views.decorators.http import require_POST

from households.utils import get_household
from recipes.utils import visible_recipes
from .models import PlannedMeal, CookedMeal
from .utils import deduct_recipe_from_pantry, visible_cooked, visible_plans

# planning meals, marking them as cooked, and the history of cooked meals


def go_back(request, fallback):
    """Sends the user back to the page they pressed the button on, or to fallback if there isn't one.

    The page comes from a hidden "next" field in the form. It's only used if it's
    a page on this site - otherwise someone could link a button to a different website.
    """
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(fallback)


@login_required
def planned_index(request):
    """The Planned Meals page. Shows every meal the household has planned, oldest first."""
    household = get_household(request.user)

    # visible_plans leaves out plans for recipes another household has since made private.
    # select_related gets each plan's recipe and who planned it in the same query,
    # instead of V1's Recipe.query.get() for every plan
    plans = visible_plans(household).select_related("recipe", "added_by")

    return render(request, "meals/planned.html", {"plans": plans})


@login_required
@require_POST
def add_to_plan(request, recipe_id):
    """Adds a recipe to the household's planned meals. One view for every "Plan this meal" button,
    since V2 recipes don't need copying into the user's account first like V1's searched ones did."""
    household = get_household(request.user)
    recipe = get_object_or_404(visible_recipes(household), pk=recipe_id)

    PlannedMeal.objects.create(household=household, recipe=recipe, added_by=request.user)

    # TODO: update the shopping list here once it's built (V1 called sync_shopping_list)

    messages.success(request, f"{recipe.name} added to Planned Meals.")
    return go_back(request, "planned:index")


@login_required
@require_POST
def remove_from_plan(request, plan_id):
    """Takes a meal off the household's plan without cooking it."""
    # visible_plans only has this household's plans, so another household's plan is a 404
    # (V1 didn't check this), and so is one whose recipe has since been made private
    plan = get_object_or_404(visible_plans(get_household(request.user)), id=plan_id)
    name = plan.recipe.name
    plan.delete()

    # TODO: update the shopping list here once it's built

    messages.success(request, f"{name} removed from Planned Meals.")
    return redirect("planned:index")

@login_required
@require_POST
def mark_as_cooked(request, plan_id):
    """Cooks a planned meal: takes its ingredients off the pantry, logs it in Cooked Meals and removes it from the plan.

    All three happen together or not at all (transaction.atomic), so a crash halfway
    can't take ingredients off the pantry without logging the meal. V1 did this with
    try/except and db.session.rollback() - atomic does the rollback for us.
    """
    household = get_household(request.user)

    with transaction.atomic():
        # select_for_update locks the plan, so if two people in the household press
        # Cook at the same moment, the second one waits, then gets a 404 because it's gone.
        # of=("self",) locks only the plan row, not the shared recipe row select_related joins in.
        # visible_plans means a plan whose recipe has since been made private can't be cooked either
        plan = get_object_or_404(
            visible_plans(household).select_for_update(of=("self",)).select_related("recipe"),
            id=plan_id,
        )
        recipe = plan.recipe

        short = deduct_recipe_from_pantry(household, recipe)
        CookedMeal.objects.create(household=household, recipe=recipe, cooked_by=request.user)
        plan.delete()

    # TODO: update the shopping list here once it's built

    messages.success(request, f"{recipe.name} cooked! Its ingredients have been taken off your pantry.")
    if short:
        messages.warning(request, f"Not enough in your pantry for: {', '.join(short)}. Whatever you had has been used up.")

    return redirect("planned:index")


@login_required
def cooked_index(request):
    """The Cooked Meals page. Shows every meal the household has cooked, newest first."""
    household = get_household(request.user)

    # newest first comes from CookedMeal's Meta ordering. visible_cooked leaves out meals whose
    # recipe another household has since made private, and select_related gets each meal's
    # recipe and who cooked it in the same query, instead of V1's Recipe.query.get() for every meal
    cooked_meals = visible_cooked(household).select_related("recipe", "cooked_by")

    for cooked in cooked_meals:
        # how long ago it was cooked, for the card. depth=1 keeps it short - "3 days", not "3 days, 2 hours"
        cooked.ago = timesince(cooked.cooked_at, depth=1)

    return render(request, "meals/cooked.html", {"cooked_meals": cooked_meals})
