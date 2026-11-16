from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from households.models import HouseholdMember
from households.utils import get_household
from .models import Recipe, SavedRecipe

# run with: python manage.py test recipes

User = get_user_model()


class SavedRecipeTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="banana", email="banana@example.com", password="pass12345")
        self.other_user = User.objects.create_user(username="apple", email="apple@example.com", password="pass12345")
        self.household = get_household(self.user)
        self.other_household = get_household(self.other_user)

        # the test database starts empty, so make a few recipes to save
        self.curry = Recipe.objects.create(name="Chicken Curry", category="Chicken", area="Indian")
        self.stew = Recipe.objects.create(name="Beef Stew", category="Beef", area="British")
        self.pancakes = Recipe.objects.create(name="Pancakes", category="Dessert", area="American")
        self.client.login(username="banana", password="pass12345")

    def make_save(self, recipe, household=None, saved_by=None):
        return SavedRecipe.objects.create(
            recipe=recipe,
            household=household or self.household,
            saved_by=saved_by or self.user,
        )

    # ---------- saving ----------

    def test_save_recipe(self):
        response = self.client.post(reverse("recipes:save", args=[self.curry.id]))
        self.assertRedirects(response, reverse("recipes:detail", args=[self.curry.id]))
        saved = SavedRecipe.objects.get()
        self.assertEqual(
            (saved.household, saved.recipe, saved.saved_by),
            (self.household, self.curry, self.user),
        )

    def test_saving_twice_only_saves_once(self):
        self.client.post(reverse("recipes:save", args=[self.curry.id]))
        # follow=True goes on to the recipe page, which is where the message shows
        response = self.client.post(reverse("recipes:save", args=[self.curry.id]), follow=True)
        self.assertContains(response, "already in your saved recipes")
        self.assertEqual(SavedRecipe.objects.count(), 1)

    def test_save_needs_post(self):
        response = self.client.get(reverse("recipes:save", args=[self.curry.id]))
        self.assertEqual(response.status_code, 405)
        self.assertFalse(SavedRecipe.objects.exists())

    def test_must_be_logged_in_to_save(self):
        self.client.logout()
        response = self.client.post(reverse("recipes:save", args=[self.curry.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SavedRecipe.objects.exists())

    def test_save_unknown_recipe_is_404(self):
        response = self.client.post(reverse("recipes:save", args=[9999]))
        self.assertEqual(response.status_code, 404)

    # ---------- removing ----------

    def test_remove_saved_recipe(self):
        self.make_save(self.curry)
        response = self.client.post(reverse("recipes:unsave", args=[self.curry.id]))
        self.assertRedirects(response, reverse("recipes:detail", args=[self.curry.id]))
        self.assertFalse(SavedRecipe.objects.exists())

    def test_remove_needs_post(self):
        self.make_save(self.curry)
        response = self.client.get(reverse("recipes:unsave", args=[self.curry.id]))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(SavedRecipe.objects.exists())

    def test_cant_remove_another_households_save(self):
        other_save = self.make_save(self.curry, household=self.other_household, saved_by=self.other_user)
        self.client.post(reverse("recipes:unsave", args=[self.curry.id]))
        self.assertTrue(SavedRecipe.objects.filter(id=other_save.id).exists())

    # ---------- recipe page ----------

    def test_recipe_page_shows_save_button(self):
        response = self.client.get(reverse("recipes:detail", args=[self.curry.id]))
        self.assertContains(response, "Save recipe")
        self.assertNotContains(response, "Remove from saved")

    def test_recipe_page_shows_remove_button_once_saved(self):
        self.make_save(self.curry)
        response = self.client.get(reverse("recipes:detail", args=[self.curry.id]))
        self.assertContains(response, "Remove from saved")
        self.assertContains(response, "Saved by you")

    # ---------- saved tab ----------

    def test_saved_tab_only_shows_your_households_saves(self):
        self.make_save(self.curry)
        self.make_save(self.stew, household=self.other_household, saved_by=self.other_user)
        response = self.client.get(reverse("recipes:index"), {"tab": "saved"})
        self.assertEqual(list(response.context["page"]), [self.curry])

    def test_saved_tab_with_nothing_saved(self):
        response = self.client.get(reverse("recipes:index"), {"tab": "saved"})
        self.assertContains(response, "Nothing saved yet")

    def test_search_on_saved_tab_only_searches_saved_recipes(self):
        self.make_save(self.curry)
        self.make_save(self.stew)
        response = self.client.get(reverse("recipes:index"), {"tab": "saved", "q": "curry"})
        self.assertEqual(list(response.context["page"]), [self.curry])
        # pancakes is a real recipe, it just isn't saved
        response = self.client.get(reverse("recipes:index"), {"tab": "saved", "q": "pancakes"})
        self.assertEqual(list(response.context["page"]), [])

    def test_all_recipes_tab_still_shows_everything(self):
        self.make_save(self.curry)
        response = self.client.get(reverse("recipes:index"))
        self.assertEqual(len(response.context["page"]), 3)
        # only the saved one gets the "Saved" badge
        self.assertEqual(response.context["saved_ids"], {self.curry.id})

    # ---------- sharing within a household ----------

    def test_household_members_share_saved_recipes(self):
        # there's no join page yet, so apple joins banana's household directly
        HouseholdMember.objects.filter(user=self.other_user).update(household=self.household, role="member")
        self.make_save(self.curry)

        self.client.login(username="apple", password="pass12345")
        response = self.client.get(reverse("recipes:index"), {"tab": "saved"})
        self.assertEqual(list(response.context["page"]), [self.curry])

        response = self.client.get(reverse("recipes:detail", args=[self.curry.id]))
        self.assertContains(response, "Saved by banana")

        # and apple can remove it, even though banana saved it
        self.client.post(reverse("recipes:unsave", args=[self.curry.id]))
        self.assertFalse(SavedRecipe.objects.exists())

    # ---------- database integrity ----------

    def test_database_blocks_saving_the_same_recipe_twice(self):
        self.make_save(self.curry)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_save(self.curry)

    def test_different_households_can_save_the_same_recipe(self):
        self.make_save(self.curry)
        self.make_save(self.curry, household=self.other_household, saved_by=self.other_user)
        self.assertEqual(SavedRecipe.objects.count(), 2)

    def test_save_stays_when_the_person_who_saved_it_is_deleted(self):
        kiwi = User.objects.create_user(username="kiwi", email="kiwi@example.com", password="pass12345")
        saved = self.make_save(self.curry, saved_by=kiwi)
        kiwi.delete()
        saved.refresh_from_db()
        self.assertIsNone(saved.saved_by)

        # the recipe page still works, it just can't say who saved it any more
        response = self.client.get(reverse("recipes:detail", args=[self.curry.id]))
        self.assertContains(response, "Saved by someone in your household")
