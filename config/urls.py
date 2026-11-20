"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import path, include
from django.views.generic import TemplateView
from allauth.account.views import LoginView


def under_construction(title, app_name):
    """A plain "Under construction" page for a nav link whose app isn't built yet.

    app_name is the name base.html already uses for the link (e.g. "cooked" for cooked:index),
    so the link works and gets highlighted in the nav. When the real app is ready, swap its line
    in urlpatterns for path('...', include('<app>.urls')) like the others - base.html doesn't change.
    """
    page = login_required(TemplateView.as_view(template_name="under_construction.html", extra_context={"title": title}))
    # include() with (url patterns, app_name) gives the page its own app name, the same as an app's urls.py does
    return include(([path("", page, name="index")], app_name))


urlpatterns = [
    path('', LoginView.as_view(), name='home'),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('settings/', include('accounts.urls')),
    path('kitchen/', include('kitchen.urls')),
    path('household/', include('households.urls')),
    path('pantry/', include('pantry.urls')),
    path('recipes/', include('recipes.urls')),
    path('suggestions/', include('suggestions.urls')),
        path('planned/', include('meals.planned_urls')),
    path('cooked/', include('meals.cooked_urls')),

    # not built yet - see under_construction above
    path('shopping/', under_construction("Shopping Lists", "shopping")),
    path('orders/', under_construction("Previous Orders", "orders")),
]
