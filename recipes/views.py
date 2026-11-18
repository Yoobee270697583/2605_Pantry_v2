from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from households.utils import get_household
from .forms import IngredientLineFormSet, RecipeForm
from .models import Ingredient, IngredientAlias, Recipe, RecipeIngredient, SavedRecipe
from .utils import visible_recipes

# how many recipe cards to show on each page
RECIPES_PER_PAGE = 24


@login_required
def index(request):
    """The My Recipes page. Has three tabs: every recipe, the ones the household has saved, and the ones it has created. All have search and category/cuisine filters."""
    active_tab = request.GET.get("tab", "all")
    # anything else, like a typo in the url, just shows all recipes
    if active_tab not in ["all", "saved", "created"]:
        active_tab = "all"

    search_query = request.GET.get("q", "").strip()
    selected_category = request.GET.get("category", "").strip()
    selected_area = request.GET.get("area", "").strip()

    household = get_household(request.user)

    # ids of every recipe this household has saved, so each card can show a "Saved" badge
    saved_ids = set(SavedRecipe.objects.filter(household=household).values_list("recipe_id", flat=True))

    # how many recipes the household has made, for the number on the Created tab
    # "custom_recipes" is the related_name on Recipe.household
    created_count = household.custom_recipes.count()

    # TheMealDB recipes, other households' custom ones that aren't private, and ours
    recipes = visible_recipes(household)

    # the saved tab only shows this household's saved recipes
    # "saves" is the related_name on SavedRecipe.recipe
    if active_tab == "saved":
        recipes = recipes.filter(saves__household=household)

    # the created tab only shows this household's own custom recipes
    elif active_tab == "created":
        recipes = recipes.filter(household=household)

    if search_query:
        recipes = recipes.filter(name__icontains=search_query)
    if selected_category:
        recipes = recipes.filter(category=selected_category)
    if selected_area:
        recipes = recipes.filter(area=selected_area)

    # dropdown options, built from the recipes this household can see
    categories = (
        visible_recipes(household).exclude(category="")
        .order_by("category")
        .values_list("category", flat=True)
        .distinct()
    )
    areas = (
        visible_recipes(household).exclude(area="")
        .order_by("area")
        .values_list("area", flat=True)
        .distinct()
    )

    paginator = Paginator(recipes, RECIPES_PER_PAGE)
    page = paginator.get_page(request.GET.get("page"))

    # the current search/filters without the page number, so the
    # previous/next links keep whatever the user searched for
    params = request.GET.copy()
    params.pop("page", None)

    return render(request, "recipes/index.html", {
        "active_tab": active_tab,
        # so each card can tell if a custom recipe is this household's own
        "household": household,
        "saved_ids": saved_ids,
        "created_count": created_count,
        "page": page,
        "total": paginator.count,
        "search_query": search_query,
        "selected_category": selected_category,
        "selected_area": selected_area,
        "categories": categories,
        "areas": areas,
        "filter_params": params.urlencode(),
    })


@login_required
def detail(request, pk):
    """Shows one recipe - its ingredients, instructions and youtube video."""
    household = get_household(request.user)

    # another household's private recipe is a 404 - visible_recipes leaves it out.
    # select_related gets who created it (for "Created by") in the same query
    recipe = get_object_or_404(visible_recipes(household).select_related("created_by"), pk=pk)

    # select_related grabs each line's ingredient in the same query,
    # ordered by id so they stay in the same order as the original recipe
    ingredients = recipe.ingredients.select_related("ingredient").order_by("id")

    # turn "https://www.youtube.com/watch?v=abc123" into an embed link for the video player
    youtube_embed_url = ""
    if "v=" in recipe.youtube_url:
        video_id = recipe.youtube_url.split("v=")[1].split("&")[0]
        youtube_embed_url = f"https://www.youtube.com/embed/{video_id}"

    # has this user's household saved it? None if not
    saved = SavedRecipe.objects.filter(
        household=household,
        recipe=recipe
    ).select_related("saved_by").first()

    return render(request, "recipes/detail.html", {
        "recipe": recipe,
        # so the page only shows edit and delete if it's this household's recipe
        "household": household,
        "ingredients": ingredients,
        "youtube_embed_url": youtube_embed_url,
        "saved": saved,
    })


@login_required
@require_POST
def save_recipe(request, pk):
    """Saves a recipe to the household's saved list."""
    household = get_household(request.user)
    recipe = get_object_or_404(visible_recipes(household), pk=pk)

    # get_or_create so pressing save twice (e.g. a double click) doesn't break anything
    saved, created = SavedRecipe.objects.get_or_create(
        household=household,
        recipe=recipe,
        defaults={"saved_by": request.user}
    )

    if created:
        messages.success(request, f"{recipe.name} saved to your recipes.")
    else:
        messages.info(request, f"{recipe.name} is already in your saved recipes.")

    return redirect("recipes:detail", pk=recipe.pk)


@login_required
@require_POST
def unsave_recipe(request, pk):
    """Removes a recipe from the household's saved list."""
    household = get_household(request.user)
    recipe = get_object_or_404(visible_recipes(household), pk=pk)

    # filtering by household means you can only ever remove your own household's saves
    SavedRecipe.objects.filter(household=household, recipe=recipe).delete()
    messages.success(request, f"{recipe.name} removed from your saved recipes.")

    return redirect("recipes:detail", pk=recipe.pk)


@login_required
def create_recipe(request):
    """The Create Recipe page. Other households can see a custom recipe unless it's private, but only the household that made it can edit or delete it."""
    form = RecipeForm(request.POST or None)
    # the prefix keeps the line fields apart from the recipe's, e.g. "lines-0-ingredient"
    lines = IngredientLineFormSet(request.POST or None, prefix="lines")

    if request.method == "POST" and form.is_valid() and lines.is_valid():
        # atomic means the recipe and its lines get saved together, or not at all
        with transaction.atomic():
            recipe = form.save(commit=False)
            recipe.source = "Custom"
            recipe.household = get_household(request.user)
            recipe.created_by = request.user
            recipe.save()
            save_lines(recipe, lines)

        messages.success(request, f"{recipe.name} created.")
        return redirect("recipes:detail", pk=recipe.pk)

    names, units = ingredient_choices()
    return render(request, "recipes/recipe_form.html", {
        "form": form,
        "lines": lines,
        "is_edit": False,
        "ingredient_names": names,
        "ingredient_units": units,
    })


@login_required
def edit_recipe(request, pk):
    """Edits one of the household's custom recipes. Anyone in the household can edit any of its recipes."""
    # filtering by household means TheMealDB recipes and other households' recipes are a 404,
    # instead of being editable (V1 didn't check who owned a recipe before letting you edit it)
    recipe = get_object_or_404(Recipe, pk=pk, household=get_household(request.user))

    # the recipe's lines as they are now, so the form starts filled in
    current_lines = []
    for line in recipe.ingredients.select_related("ingredient").order_by("id"):
        quantity = line.quantity
        # 3.0 -> 3, so the amount box doesn't show "3.0"
        if quantity is not None and quantity == int(quantity):
            quantity = int(quantity)
        current_lines.append({"ingredient": line.ingredient.name, "quantity": quantity})

    form = RecipeForm(request.POST or None, instance=recipe)
    lines = IngredientLineFormSet(request.POST or None, prefix="lines", initial=current_lines)

    if request.method == "POST" and form.is_valid() and lines.is_valid():
        with transaction.atomic():
            form.save()
            # simplest way to handle added, changed and removed lines -
            # delete the old ones and save the form's lines in their place
            recipe.ingredients.all().delete()
            save_lines(recipe, lines)

        messages.success(request, f"{recipe.name} updated.")
        return redirect("recipes:detail", pk=recipe.pk)

    names, units = ingredient_choices()
    return render(request, "recipes/recipe_form.html", {
        "form": form,
        "lines": lines,
        "recipe": recipe,
        "is_edit": True,
        "ingredient_names": names,
        "ingredient_units": units,
    })


@login_required
@require_POST
def delete_recipe(request, pk):
    """Deletes one of the household's custom recipes. POST only, so a link can't delete it."""
    recipe = get_object_or_404(Recipe, pk=pk, household=get_household(request.user))
    name = recipe.name

    # its ingredient lines and any saves get deleted with it (on_delete=CASCADE)
    recipe.delete()
    messages.success(request, f"{name} deleted.")

    return redirect(reverse("recipes:index") + "?tab=created")


def save_lines(recipe, lines):
    """Saves the ingredient lines from the form onto the recipe. Empty lines are skipped."""
    for line in lines.cleaned_data:
        if line.get("ingredient") is None:
            continue

        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=line["ingredient"],
            quantity=line["quantity"],
            # no amount (e.g. salt to taste) means it shows on the recipe but isn't taken from the pantry
            is_tracked=line["quantity"] is not None,
        )


def ingredient_choices():
    """What the ingredient boxes on the Create Recipe page need - every ingredient name to
    suggest while typing, and each name's unit to show next to the amount box."""
    names = []
    # lowercase name -> unit, e.g. "onion" -> "Each"
    units = {}

    for ingredient in Ingredient.objects.all():
        names.append(ingredient.name)
        units[ingredient.name.lower()] = ingredient.get_unit_display()

    # other names like "Onions" work too, they just aren't suggested
    for alias in IngredientAlias.objects.select_related("ingredient"):
        units[alias.name.lower()] = alias.ingredient.get_unit_display()

    return names, units
