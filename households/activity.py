# the Recent activity list on the Household page and My Kitchen - who added, planned, cooked,
# saved or ordered what. it's built from what's already saved (added_by, cooked_by, saved_by and
# their dates), so it needs no table of its own. that also means it can only show
# things that leave a record: edits, deletes and people leaving aren't shown

from django.db.models import Count
from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince

# the Household page shows this many at a time, with Newer and Older buttons
ACTIVITY_PER_PAGE = 10

# the first member counts as having started the household if they joined within this
# many seconds of it being made (households of one are made on someone's first visit)
STARTED_WITHIN_SECONDS = 60


def time_ago(when):
    """e.g. "just now", "5 minutes ago", "2 days ago" - only the biggest unit, so "2 hours" not "2 hours, 5 minutes"."""
    if (timezone.now() - when).total_seconds() < 60:
        return "just now"
    return f"{timesince(when, depth=1)} ago"


def name_for(user, viewer):
    """What to call someone in the list: "You", their first name or username, or "Someone" if their account is gone."""
    if user is None:
        return "Someone"
    if user.pk == viewer.pk:
        return "You"
    return user.first_name or user.username


def recent_activity(household, viewer, limit, skip=0):
    """Returns `limit` of the household's activity, newest first, after skipping the newest `skip`.

    Each item is a dict: when, ago ("2 hours ago"), who, and the
    sentence in parts - action, thing, after - plus url when thing can be linked to
    (a recipe, or an order on Previous Orders). e.g. "Allan" + "cooked" + "Mac n Cheese".
    """
    # imported here, not at the top - these apps import households themselves
    from meals.utils import visible_cooked, visible_plans
    from pantry.models import PantryItem
    from recipes.models import Recipe, SavedRecipe
    from recipes.utils import visible_recipes
    from shopping.models import Order

    events = []

    def add(when, user, action, thing="", after="", url=""):
        who = name_for(user, viewer)
        events.append({
            "when": when,
            "ago": time_ago(when),
            "who": who,
            # the letter in their avatar - their real initial, even when the name says "You"
            "initial": (user.first_name or user.username)[:1].upper() if user else "?",
            "action": action,
            "thing": thing,
            "after": after,
            "url": url,
        })

    # each query only fetches as many as could possibly be shown - the newest skip + limit
    limit_each = skip + limit
    pantry_items = (PantryItem.objects.filter(household=household)
                    .select_related("ingredient", "added_by").order_by("-created_at")[:limit_each])
    for item in pantry_items:
        add(item.created_at, item.added_by, "added", item.ingredient.name, "to the pantry")

    # visible_plans and visible_cooked leave out recipes another household has since
    # made private, the same as the Planned and Cooked Meals pages
    for plan in visible_plans(household).select_related("recipe", "added_by").order_by("-created_at")[:limit_each]:
        add(plan.created_at, plan.added_by, "planned", plan.recipe.name, url=reverse("recipes:detail", args=[plan.recipe_id]))

    for meal in visible_cooked(household).select_related("recipe", "cooked_by").order_by("-cooked_at")[:limit_each]:
        add(meal.cooked_at, meal.cooked_by, "cooked", meal.recipe.name, url=reverse("recipes:detail", args=[meal.recipe_id]))

    saves = (SavedRecipe.objects.filter(household=household, recipe__in=visible_recipes(household))
             .select_related("recipe", "saved_by").order_by("-saved_at")[:limit_each])
    for saved in saves:
        add(saved.saved_at, saved.saved_by, "saved", saved.recipe.name, url=reverse("recipes:detail", args=[saved.recipe_id]))

    created = (Recipe.objects.filter(household=household)
               .select_related("created_by").order_by("-created_at")[:limit_each])
    for recipe in created:
        add(recipe.created_at, recipe.created_by, "created the recipe", recipe.name, url=reverse("recipes:detail", args=[recipe.pk]))

    # checking out the shopping list. each new ingredient it puts in the pantry already shows
    # as "added ... to the pantry" - this is the shop as a whole, linked to it on Previous Orders.
    # things added to the shopping list itself aren't shown: they're deleted once they're bought
    # or taken off the list, so they'd disappear from here
    orders = (Order.objects.filter(household=household).select_related("ordered_by")
              .annotate(item_count=Count("items")).order_by("-ordered_at")[:limit_each])
    for order in orders:
        things = f"{order.item_count} item{'s' if order.item_count != 1 else ''}"
        add(order.ordered_at, order.ordered_by, "ordered", things, url=reverse("orders:detail", args=[order.pk]))

    members = list(household.members.select_related("user").order_by("joined_at", "id"))
    for position, member in enumerate(members):
        # only the first member can have started it - anyone after them joined
        seconds_after = (member.joined_at - household.created_at).total_seconds()
        if position == 0 and seconds_after < STARTED_WITHIN_SECONDS:
            add(member.joined_at, member.user, "started the household")
        else:
            add(member.joined_at, member.user, "joined the household")

    events.sort(key=lambda event: event["when"], reverse=True)
    return events[skip:skip + limit]


def activity_page(household, viewer, page):
    """One page of the Household page's activity list: (events, has_older).

    page 1 is the newest ACTIVITY_PER_PAGE. one extra is fetched to tell whether
    there's an older page, without counting everything."""
    events = recent_activity(household, viewer, limit=ACTIVITY_PER_PAGE + 1,
                             skip=(page - 1) * ACTIVITY_PER_PAGE)
    return events[:ACTIVITY_PER_PAGE], len(events) > ACTIVITY_PER_PAGE
