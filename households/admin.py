from django.contrib import admin

from .models import Household, HouseholdMember


class HouseholdMemberInline(admin.TabularInline):
    model = HouseholdMember
    extra = 0
    readonly_fields = ["joined_at"]


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ["name", "invite_code", "invite_expires_at", "created_at"]
    search_fields = ["name", "members__user__username"]
    inlines = [HouseholdMemberInline]
