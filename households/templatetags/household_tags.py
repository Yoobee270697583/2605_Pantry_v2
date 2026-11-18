from django import template

from households.forms import JoinForm
from households.models import HouseholdMember
from households.utils import current_invite_code, format_code, get_household

register = template.Library()


@register.simple_tag(takes_context=True)
def household_card(context):
    """The data for the household card on My Kitchen:
        {% load household_tags %}
        {% household_card as hh %}
        {% include "households/_kitchen_card.html" %}
    A tag, so My Kitchen's view doesn't need to know anything about households."""
    request = context["request"]
    household = get_household(request.user)
    members = list(household.members.select_related("user").order_by("joined_at", "id"))
    me = next(member for member in members if member.user_id == request.user.id)
    living_alone = len(members) == 1
    return {
        "household": household,
        "members": members,
        "is_owner": me.role == HouseholdMember.OWNER,
        "living_alone": living_alone,
        # the big invite/join card is only for people living alone - after that it's one line
        "invite_code": format_code(current_invite_code(household)) if living_alone else "",
        "join_form": JoinForm() if living_alone else None,
    }
