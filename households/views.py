from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateformat import format as format_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import JoinForm, RenameForm
from .models import HouseholdMember
from .utils import (
    HouseholdError, current_invite_code, format_code, get_household, join_household,
    leave_household, make_owner, new_invite_code, remove_member,
)

# the Household page: members, invite code, joining, leaving and the owner's actions.
# every change is a POST that redirects back, so refreshing never repeats it


def go_back(request):
    """Back to the page the button was on (My Kitchen, the Household page or Settings)."""
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("households:index")


@login_required
def index(request):
    household = get_household(request.user)
    members = household.members.select_related("user").order_by("joined_at", "id")
    me = next(member for member in members if member.user_id == request.user.id)

    return render(request, "households/index.html", {
        "household": household,
        "members": members,
        "me": me,
        "is_owner": me.role == HouseholdMember.OWNER,
        "invite_code": format_code(current_invite_code(household)),
        "join_form": JoinForm(),
        "rename_form": RenameForm(instance=household),
    })


@login_required
@require_POST
def new_code(request):
    """Only the owner can make a new code - the old one stops working straight away.

    The New code button's JavaScript (static/js/invite_code.js) gets the new code back as
    JSON and swaps it in, so the page doesn't reload. Without JavaScript it's a normal form."""
    household = get_household(request.user)
    is_owner = household.members.filter(user=request.user, role=HouseholdMember.OWNER).exists()
    from_script = request.headers.get("x-requested-with") == "XMLHttpRequest"

    if not is_owner:
        if from_script:
            return JsonResponse({"error": "Only the owner can make a new code."}, status=403)
        messages.error(request, "Only the owner can make a new code.")
        return go_back(request)

    new_invite_code(household)
    if from_script:
        return JsonResponse({
            "code": format_code(household.invite_code),
            # the time is saved in UTC. localtime changes it to NZ time first, so this is the same
            # date the page shows (the |date filter in the template does that by itself)
            "works_until": format_date(timezone.localtime(household.invite_expires_at), "j M"),
        })
    messages.success(request, "New invite code made. The old one no longer works.")
    return go_back(request)


@login_required
@require_POST
def join(request):
    form = JoinForm(request.POST)
    if form.is_valid():
        try:
            household = join_household(request.user, form.cleaned_data["code"], form.cleaned_data["bring_pantry"])
            messages.success(request, f"You've joined {household.name}. You now share its pantry.")
            return redirect("households:index")
        except HouseholdError as error:
            messages.error(request, str(error))
    else:
        messages.error(request, "Enter an invite code.")
    return go_back(request)


@login_required
@require_POST
def leave(request):
    try:
        leave_household(request.user)
        messages.success(request, "You've left the household. You're now in a household of your own.")
    except HouseholdError as error:
        messages.error(request, str(error))
    return redirect("households:index")


@login_required
@require_POST
def rename(request):
    household = get_household(request.user)
    # go_back so renaming from Settings comes back to Settings. the Household page's form
    # has no "next", so that still comes back to the Household page like before
    if not household.members.filter(user=request.user, role=HouseholdMember.OWNER).exists():
        messages.error(request, "Only the owner can rename the household.")
        return go_back(request)
    form = RenameForm(request.POST, instance=household)
    if form.is_valid():
        form.save()
        messages.success(request, "Household renamed.")
    else:
        messages.error(request, form.errors["name"][0])
    return go_back(request)


@login_required
@require_POST
def remove(request, member_id):
    try:
        member = remove_member(request.user, member_id)
        messages.success(request, f"{member.user.first_name or member.user.username} has been removed. "
                                  "Your invite code has changed, so they can't rejoin with the old one.")
    except HouseholdError as error:
        messages.error(request, str(error))
    return redirect("households:index")


@login_required
@require_POST
def promote(request, member_id):
    try:
        member = make_owner(request.user, member_id)
        messages.success(request, f"{member.user.first_name or member.user.username} is now the owner.")
    except HouseholdError as error:
        messages.error(request, str(error))
    return redirect("households:index")
