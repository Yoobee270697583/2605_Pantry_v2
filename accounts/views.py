from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import NameForm


@login_required
def settings_page(request):
    """The Settings page, from the account menu. Your name, plus your email and a link to change your password."""
    # instance=request.user so the boxes start filled in, and saving updates you instead of making a new user
    name_form = NameForm(request.POST or None, instance=request.user)

    if request.method == "POST" and name_form.is_valid():
        name_form.save()
        messages.success(request, "Your name has been updated.")
        # back to the page as a GET, so refreshing doesn't send the form again
        return redirect("accounts:settings")

    return render(request, "accounts/settings.html", {"name_form": name_form})
