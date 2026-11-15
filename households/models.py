from django.conf import settings
from django.db import models

# ============================================================================
# DATABASE MODELS
# ============================================================================
# every user is always in exactly one household. a new user gets a household
# of one (see get_household in utils.py), so someone living alone never sees
# the difference. the pantry, and later shopping lists etc, belong to the
# household rather than the user, so sharing (task 10.2) needs no schema change.
#
# joining/leaving/owner screens are task 10.1 - these tables already have
# everything those need (invite code + expiry, roles, joined date).


class Household(models.Model):
    """A group of users sharing one pantry. Most households are just one person."""

    # shown on the household page, e.g. "Banana's household" - owner can rename it (10.1)
    name = models.CharField(max_length=100)

    # code other users enter to join. empty until the owner generates one (10.1).
    # unique so a code can only ever point at one household
    invite_code = models.CharField(max_length=12, unique=True, blank=True, null=True)

    # when the current invite code stops working (codes expire after 7 days in 10.1)
    invite_expires_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class HouseholdMember(models.Model):
    """Links a user to their household. One row per user, so a user can only be in one household at a time."""

    OWNER = "owner"
    MEMBER = "member"
    ROLE_CHOICES = [
        (OWNER, "Owner"),
        (MEMBER, "Member"),
    ]

    # OneToOne = each user has at most one membership row (one household at a time).
    # settings.AUTH_USER_MODEL so this follows the custom User model once it's merged
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="household_membership"
    )

    # deleting a household deletes its memberships (10.1 moves people into
    # new households of one before that happens)
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="members"
    )

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=MEMBER)

    # used in 10.1 to pick the next owner (longest-standing member) when the owner leaves
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # a household can never have two owners
            models.UniqueConstraint(
                fields=["household"],
                condition=models.Q(role="owner"),
                name="one_owner_per_household",
            ),
            # role must be owner or member
            models.CheckConstraint(
                condition=models.Q(role__in=["owner", "member"]),
                name="household_role_valid",
            ),
        ]

    def __str__(self):
        return f"{self.user} in {self.household} ({self.role})"
