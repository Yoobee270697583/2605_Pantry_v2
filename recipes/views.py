from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from .models import Recipe

# how many recipe cards to show on each page
RECIPES_PER_PAGE = 24


@login_required
def index(request):
    """Lists the recipes in our database, with search by name and category/cuisine filters."""
    search_query = request.GET.get("q", "").strip()
    selected_category = request.GET.get("category", "").strip()
    selected_area = request.GET.get("area", "").strip()

    recipes = Recipe.objects.all()

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

    return render(request, "recipes/detail.html", {
        "recipe": recipe,
        "ingredients": ingredients,
        "youtube_embed_url": youtube_embed_url,
    })
