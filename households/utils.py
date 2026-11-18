import secrets
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Household, HouseholdMember

# how long an invite code works for
INVITE_DAYS = 7

# letters and numbers for invite codes, without ones that look alike (0/O, 1/I/L),
# so a code read out loud or copied by hand still works
CODE_CHARACTERS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6


class HouseholdError(Exception):
    """Something the user tried that isn't allowed, e.g. a wrong code. The message is shown on the page."""


def get_household(user):
    """Returns the user's household, creating a household of one if they don't have one yet.

    Every page that works with the pantry (and later shopping lists, meal
    plans etc) should start with this, so nobody can ever end up without a
    household - and it doesn't depend on the sign-up page creating one.
    """
    membership = HouseholdMember.objects.select_related("household").filter(user=user).first()
    if membership:
        return membership.household

    try:
        # atomic = the household and the membership are created together or not at all
        with transaction.atomic():
            household = Household.objects.create(name=household_name_for(user))
            HouseholdMember.objects.create(user=user, household=household, role=HouseholdMember.OWNER)
            return household
    except IntegrityError:
        # two requests arrived at the same moment and the other one already made
        # the membership - the rollback threw ours away, so use theirs
        return HouseholdMember.objects.get(user=user).household


def household_name_for(user):
    """The name a new household gets, e.g. "Banana's household"."""
    return f"{user.first_name or user.username}'s household"


# ============================================================================
# INVITE CODES
# ============================================================================

def format_code(code):
    """K7P4QX -> K7P-4QX, easier to read out. Codes are saved without the dash."""
    return f"{code[:3]}-{code[3:]}" if code else ""


def clean_code(typed):
    """What someone typed -> how codes are saved. " k7p-4qx " -> "K7P4QX"."""
    return "".join(character for character in typed.upper() if character.isalnum())


def code_is_valid(household):
    return bool(household.invite_code) and household.invite_expires_at is not None \
        and household.invite_expires_at > timezone.now()


def new_invite_code(household):
    """Gives the household a fresh code that works for INVITE_DAYS. The old code stops working."""
    for _ in range(10):
        code = "".join(secrets.choice(CODE_CHARACTERS) for _ in range(CODE_LENGTH))
        try:
            # invite_code is unique, so in the (very) rare case of a clash the save fails and we try another
            with transaction.atomic():
                household.invite_code = code
                household.invite_expires_at = timezone.now() + timedelta(days=INVITE_DAYS)
                household.save(update_fields=["invite_code", "invite_expires_at"])
            return code
        except IntegrityError:
            continue
    raise HouseholdError("Couldn't make an invite code just now. Please try again.")


def current_invite_code(household):
    """The household's working code, making a new one if it has none or the old one has expired.
    So there's always a code to share without anyone having to press a button first."""
    if not code_is_valid(household):
        new_invite_code(household)
    return household.invite_code


# ============================================================================
# JOINING, LEAVING AND OWNERS
# ============================================================================

def _lock_members(household):
    """Locks the household's membership rows until the transaction ends, so two
    people joining/leaving at the same moment can't both change who the owner is."""
    return list(HouseholdMember.objects.select_for_update().filter(household=household).order_by("joined_at", "id"))


def _hand_over_ownership(members, leaving):
    """If the owner is leaving, the longest-standing other member becomes the owner."""
    if leaving.role != HouseholdMember.OWNER:
        return
    others = [member for member in members if member.pk != leaving.pk]
    if not others:
        return
    # demote first - the database only allows one owner per household at a time
    leaving.role = HouseholdMember.MEMBER
    leaving.save(update_fields=["role"])
    others[0].role = HouseholdMember.OWNER
    others[0].save(update_fields=["role"])


def _take_all_recipes(old, new):
    """For someone living alone who joins another household: the custom recipes their household
    made (public and private) always come with them, whether or not they bring their pantry.
    A public one may be saved by other households, so it can't be deleted with the old household.
    """
    # imported here, not at the top - the recipes app imports households itself
    from recipes.models import Recipe

    Recipe.objects.filter(household=old).update(household=new)


def _bring_pantry_and_saved(old, new):
    """Moves the old household's pantry and saved recipes into the new one.

    Pantry: the same ingredient with the same expiry date (or both with no date) is added
    onto the item the household already has, e.g. 500 g flour + 1 kg flour = 1.5 kg.
    A different expiry date stays a separate item, so Expiring soon and cooking (which uses
    the soonest-expiring stock first) still know which batch goes off first.
    Units always match, since every ingredient has one unit (g, ml or each).

    Saved recipes: a recipe both households saved is only kept once.
    Planned and cooked meals don't move - they're deleted with the old household.
    """
    # imported here, not at the top - these apps import households themselves
    from pantry.models import PantryItem
    from recipes.models import SavedRecipe

    for item in PantryItem.objects.filter(household=old):
        same = PantryItem.objects.select_for_update().filter(
            household=new, ingredient_id=item.ingredient_id, expiry_date=item.expiry_date
        ) if item.expiry_date else PantryItem.objects.select_for_update().filter(
            household=new, ingredient_id=item.ingredient_id, expiry_date__isnull=True
        )
        existing = same.first()
        if existing:
            existing.quantity = round(existing.quantity + item.quantity, 2)
            existing.save(update_fields=["quantity", "updated_at"])
            item.delete()
        else:
            item.household = new
            item.save(update_fields=["household", "updated_at"])

    already_saved = set(SavedRecipe.objects.filter(household=new).values_list("recipe_id", flat=True))
    for saved in SavedRecipe.objects.filter(household=old):
        if saved.recipe_id in already_saved:
            saved.delete()
        else:
            saved.household = new
            saved.save(update_fields=["household"])


def _take_private_recipes(user, old, new):
    """Private recipes follow the person who made them when they leave a household
    (public ones stay - everyone can see those anyway).

    The old household can't see a private recipe once it's gone, so its saves, planned
    meals and cached AI tips for it are removed too. Its cooked meals history is kept,
    since that's a record of what was actually cooked.
    """
    # imported here, not at the top - the recipes and meals apps import households themselves
    from recipes.models import Recipe, SavedRecipe
    from meals.models import PlannedMeal
    from suggestions.models import SwapTip

    recipes = Recipe.objects.filter(household=old, created_by=user, is_private=True)
    recipe_ids = list(recipes.values_list("pk", flat=True))
    if not recipe_ids:
        return
    recipes.update(household=new)
    SavedRecipe.objects.filter(household=old, recipe_id__in=recipe_ids).delete()
    PlannedMeal.objects.filter(household=old, recipe_id__in=recipe_ids).delete()
    SwapTip.objects.filter(household=old, recipe_id__in=recipe_ids).delete()


def _start_own_household(member):
    """Moves a member into a new, empty household of their own, as its owner."""
    household = Household.objects.create(name=household_name_for(member.user))
    member.household = household
    member.role = HouseholdMember.OWNER
    member.joined_at = timezone.now()
    member.save(update_fields=["household", "role", "joined_at"])
    return household


def join_household(user, typed_code, bring_pantry=True):
    """Joins the household the code belongs to.

    - If the user lived alone, the recipes they made always come with them. With
      bring_pantry (the ticked-by-default box), their pantry and saved recipes come
      too, merged into the new household's. Anything left - and their planned and
      cooked meals either way - is deleted with the old household.
    - If other people stay behind, the old household's things stay with them, and
      if the user was its owner, the longest-standing member takes over. Their own
      private recipes still come with them.
    """
    code = clean_code(typed_code)
    target = Household.objects.filter(invite_code=code).first() if code else None
    if target is None or not code_is_valid(target):
        raise HouseholdError("That invite code doesn't work. Check it, or ask for a new one.")

    get_household(user)  # makes sure the user has a membership to move

    with transaction.atomic():
        member = HouseholdMember.objects.select_for_update().select_related("household").get(user=user)
        old = member.household
        if old.pk == target.pk:
            raise HouseholdError("You're already in this household.")

        # lock both households' members in id order, so two joins can't wait on each other forever
        for household in sorted([old, target], key=lambda h: h.pk):
            members = _lock_members(household)
            if household.pk == old.pk:
                old_members = members

        living_alone = len(old_members) == 1
        if living_alone:
            _take_all_recipes(old, target)
            if bring_pantry:
                _bring_pantry_and_saved(old, target)
        else:
            _hand_over_ownership(old_members, member)
            _take_private_recipes(user, old, target)

        member.household = target
        member.role = HouseholdMember.MEMBER
        member.joined_at = timezone.now()
        member.save(update_fields=["household", "role", "joined_at"])

        if living_alone:
            old.delete()

    return target


def leave_household(user):
    """Leaves the household for a new household of one. The pantry stays with the people left behind,
    but the private recipes the user made come with them."""
    with transaction.atomic():
        member = HouseholdMember.objects.select_for_update().get(user=user)
        members = _lock_members(member.household)
        if len(members) == 1:
            raise HouseholdError("You're the only one in this household, so there's nothing to leave.")
        _hand_over_ownership(members, member)
        old = member.household
        new = _start_own_household(member)
        _take_private_recipes(user, old, new)
        return new


def remove_member(owner, member_id):
    """The owner removes someone. They get a new household of their own, taking only their private recipes.
    The household gets a new invite code, so they can't rejoin with the one they already know."""
    with transaction.atomic():
        me = HouseholdMember.objects.select_for_update().get(user=owner)
        if me.role != HouseholdMember.OWNER:
            raise HouseholdError("Only the owner can remove people.")
        members = _lock_members(me.household)
        target = next((m for m in members if m.pk == member_id), None)
        if target is None:
            raise HouseholdError("That person isn't in your household.")
        if target.pk == me.pk:
            raise HouseholdError("You can't remove yourself. Use Leave household instead.")
        new = _start_own_household(target)
        _take_private_recipes(target.user, me.household, new)
        # a new code straight away, so the removed person can't just rejoin with the old one
        new_invite_code(me.household)
        return target


def make_owner(owner, member_id):
    """The owner hands ownership to another member, and becomes a normal member."""
    with transaction.atomic():
        me = HouseholdMember.objects.select_for_update().get(user=owner)
        if me.role != HouseholdMember.OWNER:
            raise HouseholdError("Only the owner can hand over ownership.")
        members = _lock_members(me.household)
        target = next((m for m in members if m.pk == member_id), None)
        if target is None or target.pk == me.pk:
            raise HouseholdError("Pick someone else in your household.")
        # demote first - the database only allows one owner per household at a time
        me.role = HouseholdMember.MEMBER
        me.save(update_fields=["role"])
        target.role = HouseholdMember.OWNER
        target.save(update_fields=["role"])
        return target
