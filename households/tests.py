from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Household, HouseholdMember
from .utils import get_household

# run with: python manage.py test households

User = get_user_model()


class HouseholdTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="banana", email="banana@example.com", password="pass12345", first_name="Banana")

    def test_new_user_gets_household_of_one(self):
        household = get_household(self.user)
        self.assertEqual(household.name, "Banana's household")
        member = HouseholdMember.objects.get(user=self.user)
        self.assertEqual((member.household, member.role), (household, "owner"))

    def test_same_household_every_time(self):
        self.assertEqual(get_household(self.user), get_household(self.user))
        self.assertEqual(Household.objects.count(), 1)

    def test_uses_username_when_no_first_name(self):
        user = User.objects.create_user(username="alex", email="alex@example.com", password="pass12345")
        self.assertEqual(get_household(user).name, "alex's household")

    def test_user_can_only_be_in_one_household(self):
        get_household(self.user)
        other = Household.objects.create(name="Other")
        with self.assertRaises(IntegrityError), transaction.atomic():
            HouseholdMember.objects.create(user=self.user, household=other)

    def test_household_cant_have_two_owners(self):
        household = get_household(self.user)
        alex = User.objects.create_user(username="alex", email="alex@example.com", password="pass12345")
        with self.assertRaises(IntegrityError), transaction.atomic():
            HouseholdMember.objects.create(user=alex, household=household, role="owner")

    def test_household_can_have_several_members(self):
        household = get_household(self.user)
        alex = User.objects.create_user(username="alex", email="alex@example.com", password="pass12345")
        HouseholdMember.objects.create(user=alex, household=household, role="member")
        self.assertEqual(household.members.count(), 2)
        self.assertEqual(get_household(alex), household)
