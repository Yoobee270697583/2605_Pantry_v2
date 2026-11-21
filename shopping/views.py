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
from .models import Order, ShoppingItem
from .utils import ShoppingError, add_list_to_pantry, get_shopping_list

# the shopping list - what to buy for the household's planned meals, plus the things people add
# themselves, and adding what's been bought to the pantry. the last two views are Previous Orders

# the most ingredients one search shows. each one has its own little form, so 650 of them
# (searching "a") would be a very long page
MAX_SEARCH_RESULTS = 20

# how many ingredient names each order shows on Previous Orders, before "and 11 more"
ORDER_PREVIEW_NAMES = 3


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


@login_required
@require_POST
def add_to_pantry(request):
    """Adds one row of the shopping list to the pantry - the row whose Add to pantry button was pressed.
    Doesn't make an order, the same as V1's Add to Pantry button."""
    household = get_household(request.user)

    # the button's value says which row it's on, e.g. "planned_12" (see the template)
    row = request.POST.get("row", "")
    try:
        # a single row never makes an order, so the second thing it gives back isn't needed here
        added, order = add_list_to_pantry(household, request.user, request.POST, only_row=row)
    except ShoppingError as error:
        messages.error(request, str(error))
        return redirect("shopping:index")

    # nothing added means the row had already gone (someone else in the household just bought it,
    # or a double click). the page they're sent back to shows the list as it is now, so no message
    if added:
        messages.success(request, f"{added[0]} added to your pantry.")
    return redirect("shopping:index")


@login_required
@require_POST
def checkout(request):
    """Adds everything on the shopping list to the pantry in one go, and saves it as an order.
    V1 called this checkout too - its button was Add List To Pantry."""
    household = get_household(request.user)

    try:
        added, order = add_list_to_pantry(household, request.user, request.POST)
    except ShoppingError as error:
        messages.error(request, str(error))
        return redirect("shopping:index")

    if not added:
        messages.info(request, "Nothing was added to your pantry. Rows with an empty box are skipped.")
        return redirect("shopping:index")

    messages.success(request, f"{len(added)} thing{'s' if len(added) != 1 else ''} added to your pantry.")
    # straight to the order it just made, so you can see what went in (V1 went to the list of orders)
    return redirect("orders:detail", order.id)


@login_required
def orders_index(request):
    """The Previous Orders page. Every shopping list the household has added to its pantry, newest first."""
    household = get_household(request.user)

    # newest first comes from Order's Meta ordering. prefetch_related gets the lines of every order,
    # and their ingredients, in two more queries - not a query for each order like V1's order.items
    orders = (
        Order.objects.filter(household=household)
        .select_related("ordered_by")
        .prefetch_related("items__ingredient")
    )

    for order in orders:
        # the lines come out A to Z (OrderItem's Meta ordering). a few of the names go on the page,
        # with how many more there are, so you can tell which shop was which
        names = [item.ingredient.name for item in order.items.all()]
        order.item_count = len(names)
        order.preview = ", ".join(names[:ORDER_PREVIEW_NAMES])
        order.more_count = max(len(names) - ORDER_PREVIEW_NAMES, 0)

    return render(request, "shopping/orders.html", {"orders": orders})


@login_required
def order_detail(request, order_id):
    """One order: everything it added to the pantry, and how much."""
    # filtering by household means another household's order is a 404 (V1 sent you back to the list)
    order = get_object_or_404(
        Order.objects.select_related("ordered_by"),
        id=order_id,
        household=get_household(request.user),
    )

    return render(request, "shopping/order_detail.html", {
        "order": order,
        # select_related gets each line's ingredient in the same query
        "items": order.items.select_related("ingredient"),
    })
