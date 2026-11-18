from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from households.forms import RenameForm
from households.models import HouseholdMember
from households.utils import get_household
from .forms import NameForm


@login_required
def settings_page(request):
    """The Settings page, from the account menu. Your name, your email and password, and your household."""
    # instance=request.user so the boxes start filled in, and saving updates you instead of making a new user
    name_form = NameForm(request.POST or None, instance=request.user)

    if request.method == "POST" and name_form.is_valid():
        name_form.save()
        messages.success(request, "Your name has been updated.")
        # back to the page as a GET, so refreshing doesn't send the form again
        return redirect("accounts:settings")

    household = get_household(request.user)
    # only the owner can rename the household, the same rule as the Household page
    is_owner = household.members.filter(user=request.user, role=HouseholdMember.OWNER).exists()

    return render(request, "accounts/settings.html", {
        "name_form": name_form,
        "household": household,
        "is_owner": is_owner,
        "member_count": household.members.count(),
        # Brix's form from the Household page - it posts to households:rename, which brings you back here
        "rename_form": RenameForm(instance=household),
    })
