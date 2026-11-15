from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from households.models import HouseholdMember
from households.utils import get_household
from recipes.models import Ingredient
from .models import PantryItem

# run with: python manage.py test pantry

User = get_user_model()


class PantryTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="banana", email="banana@example.com", password="pass12345")
        self.other_user = User.objects.create_user(username="apple", email="apple@example.com", password="pass12345")
        self.household = get_household(self.user)
        self.other_household = get_household(self.other_user)

        self.onion = Ingredient.objects.create(name="Onion", unit="each")
        self.flour = Ingredient.objects.create(name="Plain Flour", unit="g")
        self.client.login(username="banana", password="pass12345")

    def make_item(self, household=None, ingredient=None, **kwargs):
        return PantryItem.objects.create(
            household=household or self.household,
            added_by=kwargs.get("added_by", self.user),
            ingredient=ingredient or self.onion,
            quantity=kwargs.get("quantity", 2),
            category=kwargs.get("category", "fruit_veg"),
            expiry_date=kwargs.get("expiry_date"),
        )

    # ---------- viewing ----------

    def test_must_be_logged_in(self):
        self.client.logout()
        response = self.client.get(reverse("pantry:index"))
        self.assertEqual(response.status_code, 302)

    def test_only_shows_your_households_items(self):
        self.make_item()
        self.make_item(household=self.other_household, ingredient=self.flour, added_by=self.other_user)
        response = self.client.get(reverse("pantry:index"))
        self.assertContains(response, "Onion")
        self.assertNotContains(response, "Plain Flour")

    def test_first_visit_creates_household_of_one(self):
        new_user = User.objects.create_user(username="kiwi", email="kiwi@example.com", password="pass12345")
        self.client.login(username="kiwi", password="pass12345")
        self.client.get(reverse("pantry:index"))
        self.assertTrue(HouseholdMember.objects.filter(user=new_user, role="owner").exists())

    def test_search_and_category_filter(self):
        onion_item = self.make_item()
        flour_item = self.make_item(ingredient=self.flour, category="pantry_staples")
        response = self.client.get(reverse("pantry:index"), {"q": "flour"})
        self.assertEqual(list(response.context["pantry_items"]), [flour_item])
        response = self.client.get(reverse("pantry:index"), {"category": "fruit_veg"})
        self.assertEqual(list(response.context["pantry_items"]), [onion_item])

    def test_ingredient_search(self):
        response = self.client.get(reverse("pantry:index"), {"tab": "ingredients", "q": "oni"})
        self.assertContains(response, "Onion")
        self.assertNotContains(response, "Plain Flour")

    # ---------- adding ----------

    def test_add_item(self):
        response = self.client.post(reverse("pantry:add", args=[self.flour.id]), {
            "quantity": "500", "category": "pantry_staples", "expiry_date": "",
        })
        self.assertRedirects(response, reverse("pantry:index"))
        item = PantryItem.objects.get()
        self.assertEqual(
            (item.household, item.added_by, item.ingredient, item.quantity),
            (self.household, self.user, self.flour, 500),
        )

    def test_add_rejects_bad_values(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        response = self.client.post(reverse("pantry:add", args=[self.flour.id]), {
            "quantity": "0", "category": "pantry_staples", "expiry_date": yesterday.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("quantity", response.context["form"].errors)
        self.assertIn("expiry_date", response.context["form"].errors)
        self.assertFalse(PantryItem.objects.exists())

    def test_add_unknown_ingredient_is_404(self):
        response = self.client.get(reverse("pantry:add", args=[9999]))
        self.assertEqual(response.status_code, 404)

    # ---------- editing ----------

    def test_edit_item(self):
        item = self.make_item()
        self.client.post(reverse("pantry:edit", args=[item.id]), {
            "quantity": "5", "category": "other", "expiry_date": "",
        })
        item.refresh_from_db()
        self.assertEqual((item.quantity, item.category), (5, "other"))

    def test_can_edit_already_expired_item_without_changing_date(self):
        old_date = timezone.localdate() - timedelta(days=3)
        item = self.make_item(expiry_date=old_date)
        self.client.post(reverse("pantry:edit", args=[item.id]), {
            "quantity": "1", "category": "fruit_veg", "expiry_date": old_date.isoformat(),
        })
        item.refresh_from_db()
        self.assertEqual(item.quantity, 1)

    def test_cant_edit_another_households_item(self):
        item = self.make_item(household=self.other_household, added_by=self.other_user)
        response = self.client.post(reverse("pantry:edit", args=[item.id]), {
            "quantity": "99", "category": "other", "expiry_date": "",
        })
        self.assertEqual(response.status_code, 404)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)

    # ---------- deleting ----------

    def test_delete_item(self):
        item = self.make_item()
        self.client.post(reverse("pantry:delete", args=[item.id]))
        self.assertFalse(PantryItem.objects.filter(id=item.id).exists())

    def test_delete_needs_post(self):
        item = self.make_item()
        response = self.client.get(reverse("pantry:delete", args=[item.id]))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(PantryItem.objects.filter(id=item.id).exists())

    def test_cant_delete_another_households_item(self):
        item = self.make_item(household=self.other_household, added_by=self.other_user)
        response = self.client.post(reverse("pantry:delete", args=[item.id]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(PantryItem.objects.filter(id=item.id).exists())

    # ---------- sharing within a household ----------

    def test_household_members_share_one_pantry(self):
        # apple joins banana's household (the join screen is 10.1 - done directly here)
        HouseholdMember.objects.filter(user=self.other_user).update(household=self.household, role="member")
        item = self.make_item(added_by=self.user)

        self.client.login(username="apple", password="pass12345")
        response = self.client.get(reverse("pantry:index"))
        self.assertContains(response, "Onion")

        # and can edit it, even though banana added it
        self.client.post(reverse("pantry:edit", args=[item.id]), {
            "quantity": "7", "category": "fruit_veg", "expiry_date": "",
        })
        item.refresh_from_db()
        self.assertEqual(item.quantity, 7)

    # ---------- database integrity ----------

    def test_database_blocks_negative_quantity(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_item(quantity=-1)

    def test_database_blocks_unknown_category(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_item(category="not_a_category")

    def test_item_stays_when_the_person_who_added_it_is_deleted(self):
        alex = User.objects.create_user(username="alex", email="alex@example.com", password="pass12345")
        item = self.make_item(added_by=alex)
        alex.delete()
        item.refresh_from_db()
        self.assertIsNone(item.added_by)
