from django.contrib import admin

from .models import SwapTip


# so we can see how much the AI swap tips are being used
@admin.register(SwapTip)
class SwapTipAdmin(admin.ModelAdmin):
    list_display = ["recipe", "household", "asked_by", "created_at"]
    search_fields = ["recipe__name", "household__name"]
