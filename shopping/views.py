import math

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from households.utils import get_household
from meals.utils import visible_plans
from meals.views import go_back
from recipes.models import Ingredient
from .forms import AmountForm
from .models import ShoppingItem
from .utils import get_shopping_list

# the shopping list - what to buy for the household's planned meals, plus the things people add themselves

# the most ingredients one search shows. each one has its own little form, so 650 of them
# (searching "a") would be a very long page
MAX_SEARCH_RESULTS = 20


@login_required
def index(request):
    """The Shopping List page. Shows what the household needs to buy for its planned meals,
    the things it added itself, and a search for adding more."""
    household = get_household(request.user)
    search_query = request.GET.get("q", "").strip()

    # the things people added themselves. select_related gets each one's ingredient and who
    # added it in the same query
    own_items = ShoppingItem.objects.filter(household=household).select_related("ingredient", "added_by")

    context = {
        "shopping_list": get_shopping_list(household),
        # how many meals the list is for. also tells "nothing planned" apart from "you have everything"
        "planned_count": visible_plans(household).count(),
        "own_items": own_items,
        "search_query": search_query,
    }

    if search_query:
        # any ingredient can be added, even staples like Salt that the planned meals part leaves out
        matches = list(Ingredient.objects.filter(name__icontains=search_query))

        # names that start with what was typed go first, so searching "milk" gives Milk before
        # Almond Milk. they come out of the database A to Z and sort() keeps that order inside each half
        matches.sort(key=lambda ingredient: not ingredient.name.lower().startswith(search_query.lower()))
        found = matches[:MAX_SEARCH_RESULTS]

        # how much of each one is on the list already, to show next to it
        on_list = {item.ingredient_id: item.quantity for item in own_items}
        for ingredient in found:
            ingredient.on_list = on_list.get(ingredient.id)

        context["found_ingredients"] = found
        # how many more there were than the page shows
        context["hidden_count"] = len(matches) - len(found)

    return render(request, "shopping/index.html", context)


@login_required
@require_POST
def add_item(request, ingredient_id):
    """Adds an ingredient from the search results to the household's own items.
    If it's already one of them, the amount is added onto that row instead of making a second one."""
    household = get_household(request.user)
    ingredient = get_object_or_404(Ingredient, id=ingredient_id)

    form = AmountForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.errors["quantity"][0])
        return go_back(request, "shopping:index")

    quantity = form.cleaned_data["quantity"]
    if ingredient.unit == "each":
        # things that are counted go up to a whole one, the same as the planned meals part of the list
        quantity = math.ceil(quantity)

    with transaction.atomic():
        # select_for_update locks the row if it's already there, so two people in the household
        # adding the same thing at the same moment both get counted. get_or_create also copes with
        # both of them trying to make the row at once (the database only allows one per ingredient)
        item, created = ShoppingItem.objects.select_for_update().get_or_create(
            household=household,
            ingredient=ingredient,
            defaults={"quantity": quantity, "added_by": request.user},
        )
        if not created:
            # rounded so float maths can't leave 0.30000000000000004 on the list
            item.quantity = round(item.quantity + quantity, 2)
            item.save(update_fields=["quantity"])

    if created:
        messages.success(request, f"{ingredient.name} added to your shopping list.")
    else:
        messages.success(request, f"{ingredient.name} was already on your shopping list, so this was added onto it.")

    # back to the search they added it from, so they can add something else from it
    return go_back(request, "shopping:index")


@login_required
@require_POST
def remove_item(request, item_id):
    """Takes one of the household's own items off the shopping list. POST only, so a link can't remove things."""
    # filtering by household means another household's item is a 404 (V1 checked the user here too)
    item = get_object_or_404(ShoppingItem, id=item_id, household=get_household(request.user))
    name = item.ingredient.name
    item.delete()

    messages.success(request, f"{name} removed from your shopping list.")
    return redirect("shopping:index")
