from django.contrib.auth.decorators import login_required
from django.shortcuts import render

# suggests recipes the household can make (or nearly make) with what's in its pantry


@login_required
def index(request):
    """The Suggested Recipes page. Just the page for now - the suggestions themselves get added next."""
    return render(request, "suggestions/index.html")
