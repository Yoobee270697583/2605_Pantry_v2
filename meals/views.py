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

#=============================================================
#                       PLANNED  MEALS                       #
#=============================================================

def go_back(request, fallback):
    """ Sends the user back to the page they pressed the button on, or to a fallback if there isn't one.
        The page comes from a hidden "next" field in the form. It's only used if it's
        a page on this site - otherwise someone could link a button to a different website."""
    
    # Save the url/address of the page the request came from
    next_url = request.POST.get("next", "")
    # Check that the url is from and approved by our app
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        # If it is, send the user there (sending them to where they were when they clicked the given button)
        return redirect(next_url)
    # Otherwise, send them to a fallback location in the app, if there is no appropriate request
    return redirect(fallback)


# User must be authenticated via allauth, else they are immediatly redirected to the login screen
@login_required
def planned_index(request):
    """The Planned Meals page. Shows every meal the household has planned, oldest first."""
    # The household in question
    household = get_household(request.user)
    # Visible_plans leaves out plans for recipes another household has since made private.
    # Select_related gets each plan's recipe and who planned it in the same query,
    plans = visible_plans(household).select_related("recipe", "added_by")
    # Return the rendered template with the request and the planned meals data
    return render(request, "meals/planned.html", {"plans": plans})


# User must be authenticated
@login_required
# The view rejects anything that isn't a POST
@require_POST
def add_to_plan(request, recipe_id):
    """Adds a recipe to the household's planned meals. One view for every "Plan this meal" button,
    since V2 recipes don't need copying into the user's account first like V1's searched ones did."""
    # The household in question
    household = get_household(request.user)
    # Save the currently visible recipes of the given household to a recipes variable
    recipes = get_object_or_404(visible_recipes(household), pk=recipe_id)
    # Make a new object of the recipe that gets planned, associated to the current user and household
    PlannedMeal.objects.create(household=household, recipe=recipes, added_by=request.user)
    # Save a success message about the meal being planned
    messages.success(request, f"{recipes.name} added to Planned Meals.")
    # Return the user to where they were, with the request data, or otherwise send them to planned meals index page (via go_back(..))
    return go_back(request, "planned:index")


@login_required
@require_POST
def remove_from_plan(request, plan_id):
    """Takes a meal off the household's planed meals without cooking it."""
    # visible_plans only has this household's plans, so another household's plan is a 404
    # and so is one whose recipe has since been made private

    # The planned meal
    plan = get_object_or_404(visible_plans(get_household(request.user)), id=plan_id)
    # The recipe's name
    name = plan.recipe.name
    # Delete the plan
    plan.delete()
    # Save a success message about the planned meal being deleted
    messages.success(request, f"{name} removed from Planned Meals.")
    # Return the Planned Meals index page
    return redirect("planned:index")


#=============================================================
#                       COOKED MEALS                         #
#=============================================================

@login_required
@require_POST
def mark_as_cooked(request, plan_id):
    """Cooks a planned meal: takes its ingredients off the pantry, logs it in Cooked Meals and removes it from the plan.
        All three happen together or not at all (transaction.atomic), so a crash halfway
        can't take ingredients off the pantry without logging the meal. V1 did this with
        try/except and db.session.rollback() - atomic does the rollback for us. """

    # The household in question        
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

    # the shopping list doesn't need updating here either - see add_to_plan

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


@login_required
@require_POST
def delete_cooked(request, cooked_id):
    """Takes a meal out of the household's Cooked Meals history. The pantry doesn't change, the same as V1's Delete."""
    # visible_cooked only has this household's meals, so another household's is a 404 (V1 didn't check this)
    cooked = get_object_or_404(visible_cooked(get_household(request.user)), id=cooked_id)
    name = cooked.recipe.name
    cooked.delete()

    messages.success(request, f"{name} removed from Cooked Meals.")
    return redirect("cooked:index")
