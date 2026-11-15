from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def index(request):
    """My Kitchen home page. Placeholder until the real dashboard is built."""
    return render(request, "kitchen/index.html")