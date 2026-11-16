from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from households.utils import get_household
from .models import Recipe, SavedRecipe

# how many recipe cards to show on each page
RECIPES_PER_PAGE = 24


@login_required
def index(request):
    """The My Recipes page. Has two tabs: every recipe, and the ones the household has saved. Both have search and category/cuisine filters."""
    active_tab = request.GET.get("tab", "all")
    search_query = request.GET.get("q", "").strip()
    selected_category = request.GET.get("category", "").strip()
    selected_area = request.GET.get("area", "").strip()

    household = get_household(request.user)

    # ids of every recipe this household has saved, so each card can show a "Saved" badge
    saved_ids = set(SavedRecipe.objects.filter(household=household).values_list("recipe_id", flat=True))

    recipes = Recipe.objects.all()

    # the saved tab only shows this household's saved recipes
    # "saves" is the related_name on SavedRecipe.recipe
    if active_tab == "saved":
        recipes = recipes.filter(saves__household=household)

    if search_query:
        recipes = recipes.filter(name__icontains=search_query)
    if selected_category:
        recipes = recipes.filter(category=selected_category)
    if selected_area:
        recipes = recipes.filter(area=selected_area)

    # dropdown options, built from the recipes we actually have
    categories = (
        Recipe.objects.exclude(category="")
        .order_by("category")
        .values_list("category", flat=True)
        .distinct()
    )
    areas = (
        Recipe.objects.exclude(area="")
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
        "saved_ids": saved_ids,
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
    recipe = get_object_or_404(Recipe, pk=pk)

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
        household=get_household(request.user),
        recipe=recipe
    ).select_related("saved_by").first()

    return render(request, "recipes/detail.html", {
        "recipe": recipe,
        "ingredients": ingredients,
        "youtube_embed_url": youtube_embed_url,
        "saved": saved,
    })


@login_required
@require_POST
def save_recipe(request, pk):
    """Saves a recipe to the household's saved list."""
    recipe = get_object_or_404(Recipe, pk=pk)

    # get_or_create so pressing save twice (e.g. a double click) doesn't break anything
    saved, created = SavedRecipe.objects.get_or_create(
        household=get_household(request.user),
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
    recipe = get_object_or_404(Recipe, pk=pk)

    # filtering by household means you can only ever remove your own household's saves
    SavedRecipe.objects.filter(household=get_household(request.user), recipe=recipe).delete()
    messages.success(request, f"{recipe.name} removed from your saved recipes.")

    return redirect("recipes:detail", pk=recipe.pk)
