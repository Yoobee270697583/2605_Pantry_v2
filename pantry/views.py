from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from households.utils import get_household
from recipes.models import CATEGORY_CHOICES, Ingredient
from .forms import PantryItemForm
from .models import PantryItem

# viewing/searching the pantry, browsing ingredients, and adding/editing/deleting pantry items


@login_required
def index(request):
    """The My Pantry page. Has two tabs: the household's pantry items, and the ingredient list to add from."""
    active_tab = request.GET.get("tab", "pantry")
    search_query = request.GET.get("q", "").strip()

    context = {
        "active_tab": active_tab,
        "search_query": search_query,
        "category_choices": CATEGORY_CHOICES,
    }

    if active_tab == "ingredients":
        # every ingredient A-Z, so people can browse by category or search
        selected_category = request.GET.get("category", "").strip()
        ingredients = Ingredient.objects.all()

        if search_query:
            ingredients = ingredients.filter(name__icontains=search_query)
        if selected_category:
            ingredients = ingredients.filter(category=selected_category)

        # 25 cards a page
        page = Paginator(ingredients, 25).get_page(request.GET.get("page"))

        context["ingredients"] = page
        context["page"] = page
        context["selected_category"] = selected_category

    else:
        selected_category = request.GET.get("category", "").strip()

        # only ever this household's items (a household of one for most people)
        household = get_household(request.user)
        items = PantryItem.objects.filter(household=household).select_related("ingredient", "added_by")

        if search_query:
            items = items.filter(ingredient__name__icontains=search_query)
        if selected_category:
            # the category comes from the ingredient, not the pantry item
            items = items.filter(ingredient__category=selected_category)

        context["pantry_items"] = items
        context["selected_category"] = selected_category
        # used to mark expired items in the table
        context["today"] = timezone.localdate()
        context["has_any_items"] = PantryItem.objects.filter(household=household).exists()
        # "Added by" only shows when the pantry is shared with someone else
        context["is_shared"] = household.members.count() > 1

    return render(request, "pantry/pantry.html", context)


@login_required
def add_item(request, ingredient_id):
    """Adds the ingredient picked on the Ingredients tab to the household's pantry."""
    ingredient = get_object_or_404(Ingredient, id=ingredient_id)
    form = PantryItemForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.household = get_household(request.user)
        item.added_by = request.user
        item.ingredient = ingredient
        item.save()
        messages.success(request, f"{ingredient.name} added to your pantry.")
        return redirect("pantry:index")

    return render(request, "pantry/pantry_item_form.html", {
        "form": form,
        "ingredient": ingredient,
        "is_edit": False,
    })


@login_required
def edit_item(request, item_id):
    """Edits one of the household's pantry items. Anyone in the household can edit any of its items."""
    # filtering by household means you get a 404 for another household's item,
    # instead of being able to edit it (V1 didn't check this)
    item = get_object_or_404(PantryItem, id=item_id, household=get_household(request.user))
    form = PantryItemForm(request.POST or None, instance=item)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{item.ingredient.name} updated.")
        return redirect("pantry:index")

    return render(request, "pantry/pantry_item_form.html", {
        "form": form,
        "ingredient": item.ingredient,
        "item": item,
        "is_edit": True,
    })


@login_required
@require_POST
def delete_item(request, item_id):
    """Deletes one of the household's pantry items. POST only, so a link can't delete things."""
    item = get_object_or_404(PantryItem, id=item_id, household=get_household(request.user))
    name = item.ingredient.name
    item.delete()
    messages.success(request, f"{name} removed from your pantry.")
    return redirect("pantry:index")
