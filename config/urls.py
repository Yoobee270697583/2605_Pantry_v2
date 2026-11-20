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
from django.urls import path, include
from allauth.account.views import LoginView

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
    path('shopping/', include('shopping.urls')),
    path('orders/', include('shopping.orders_urls')),
]
