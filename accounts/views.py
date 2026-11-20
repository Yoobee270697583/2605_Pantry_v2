from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from allauth.socialaccount.models import SocialAccount

from households.forms import RenameForm
from households.models import HouseholdMember
from households.utils import get_household
from .forms import NameForm


@login_required
def settings_page(request):
    """The Settings page, from the account menu. Your name, your email, password and Google login, and your household."""
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
        # the Google account this user has connected - None if they only log in with a password
        "google_account": SocialAccount.objects.filter(user=request.user, provider="google").first(),
    })


@login_required
@require_POST
def disconnect_google(request):
    """Takes the Google account off this user, so Continue with Google stops logging into it. POST only, so a link can't do it."""
    # someone who signed up with Google has no password, so Google is their only way in.
    # the page hides the button for them, this is for a POST sent without the page
    if not request.user.has_usable_password():
        messages.error(request, "Set a password first, or you won't be able to log in.")
        return redirect("accounts:settings")

    google_account = SocialAccount.objects.filter(user=request.user, provider="google").first()
    if google_account:
        google_account.delete()
        messages.success(request, "Your Google account has been disconnected.")

    return redirect("accounts:settings")
