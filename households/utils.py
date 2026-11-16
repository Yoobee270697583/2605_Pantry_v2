from django.db import IntegrityError, transaction

from .models import Household, HouseholdMember


def get_household(user):
    """Returns the user's household, creating a household of one if they don't have one yet.

    Every page that works with the pantry (and later shopping lists, meal
    plans etc) should start with this, so nobody can ever end up without a
    household - and it doesn't depend on the sign-up page creating one.
    """
    membership = HouseholdMember.objects.select_related("household").filter(user=user).first()
    if membership:
        return membership.household

    name = f"{user.first_name or user.username}'s household"

    try:
        # atomic = the household and the membership are created together or not at all
        with transaction.atomic():
            household = Household.objects.create(name=name)
            HouseholdMember.objects.create(user=user, household=household, role=HouseholdMember.OWNER)
            return household
    except IntegrityError:
        # two requests arrived at the same moment and the other one already made
        # the membership - the rollback threw ours away, so use theirs
        return HouseholdMember.objects.get(user=user).household
