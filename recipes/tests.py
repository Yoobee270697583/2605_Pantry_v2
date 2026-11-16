from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from households.models import HouseholdMember
from households.utils import get_household
from .models import Ingredient, IngredientAlias, Recipe, RecipeIngredient, SavedRecipe

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


class CustomRecipeTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="banana", email="banana@example.com", password="pass12345")
        self.other_user = User.objects.create_user(username="apple", email="apple@example.com", password="pass12345")
        self.household = get_household(self.user)
        self.other_household = get_household(self.other_user)

        # the test database starts empty, so make the ingredients the form can pick from
        self.onion = Ingredient.objects.create(name="Onion", unit="each")
        self.butter = Ingredient.objects.create(name="Butter", unit="g")
        self.salt = Ingredient.objects.create(name="Salt", unit="ml")
        # merge_ingredients would normally make this one
        IngredientAlias.objects.create(name="Onions", ingredient=self.onion)

        # a TheMealDB recipe - the category and cuisine dropdowns get their options from these
        self.curry = Recipe.objects.create(name="Chicken Curry", category="Chicken", area="Indian")
        self.client.login(username="banana", password="pass12345")

    def recipe_data(self, lines, initial_lines=0, **details):
        """What the Create/Edit Recipe form sends. lines is a list of (ingredient, amount)."""
        data = {
            "name": "Onion Soup",
            "category": "",
            "area": "",
            "image_url": "",
            "instructions": "Cook the onions in the butter.",
            # the formset's management form - how many lines were sent
            "lines-TOTAL_FORMS": len(lines),
            "lines-INITIAL_FORMS": initial_lines,
        }
        data.update(details)
        for i, (ingredient, quantity) in enumerate(lines):
            data[f"lines-{i}-ingredient"] = ingredient
            data[f"lines-{i}-quantity"] = quantity
        return data

    def make_recipe(self, household=None, created_by=None):
        """A custom recipe with 3 onions in it, made straight in the database."""
        recipe = Recipe.objects.create(
            name="Onion Soup",
            source="Custom",
            household=household or self.household,
            created_by=created_by or self.user,
            instructions="Cook the onions.",
        )
        RecipeIngredient.objects.create(recipe=recipe, ingredient=self.onion, quantity=3)
        return recipe

    def lines_of(self, recipe):
        """(ingredient, quantity, is_tracked) for each of a recipe's lines, in order."""
        lines = []
        for line in recipe.ingredients.order_by("id"):
            lines.append((line.ingredient, line.quantity, line.is_tracked))
        return lines

    # ---------- creating ----------

    def test_create_recipe(self):
        data = self.recipe_data(
            [("Onion", "3"), ("Butter", "50"), ("Salt", ""), ("", "")],
            category="Chicken",
            image_url="example.com/soup.jpg",
        )
        response = self.client.post(reverse("recipes:create"), data)

        recipe = Recipe.objects.get(source="Custom")
        self.assertRedirects(response, reverse("recipes:detail", args=[recipe.id]))
        self.assertEqual(
            (recipe.name, recipe.category, recipe.household, recipe.created_by),
            ("Onion Soup", "Chicken", self.household, self.user),
        )
        # https:// gets added to links that don't have it
        self.assertEqual(recipe.image_url, "https://example.com/soup.jpg")
        # salt has no amount so it isn't tracked, and the empty line is skipped
        self.assertEqual(self.lines_of(recipe), [
            (self.onion, 3, True),
            (self.butter, 50, True),
            (self.salt, None, False),
        ])

    def test_create_page_lists_our_ingredients(self):
        response = self.client.get(reverse("recipes:create"))
        self.assertEqual(response.context["ingredient_names"], ["Butter", "Onion", "Salt"])
        # other names get a unit too, so typing "onions" still shows Each
        self.assertEqual(response.context["ingredient_units"]["onions"], "Each")

    def test_must_be_logged_in_to_create(self):
        self.client.logout()
        response = self.client.post(reverse("recipes:create"), self.recipe_data([("Onion", "3")]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Recipe.objects.filter(source="Custom").exists())

    def test_ingredient_can_be_typed_with_another_name(self):
        # "onions" was merged into Onion, and upper/lower case doesn't matter
        self.client.post(reverse("recipes:create"), self.recipe_data([("onions", "2")]))
        recipe = Recipe.objects.get(source="Custom")
        self.assertEqual(self.lines_of(recipe), [(self.onion, 2, True)])

    def test_unknown_ingredient(self):
        response = self.client.post(reverse("recipes:create"), self.recipe_data([("Unicorn Tears", "1")]))
        self.assertContains(response, "Pick an ingredient from the list.")
        self.assertFalse(Recipe.objects.filter(source="Custom").exists())

    def test_same_ingredient_twice(self):
        # Onions is another name for Onion, so this is still the same ingredient twice
        response = self.client.post(reverse("recipes:create"), self.recipe_data([("Onion", "1"), ("Onions", "2")]))
        self.assertContains(response, "Onion is on the list twice.")
        self.assertFalse(Recipe.objects.filter(source="Custom").exists())

    def test_recipe_needs_an_ingredient(self):
        response = self.client.post(reverse("recipes:create"), self.recipe_data([("", ""), ("", "")]))
        self.assertContains(response, "Add at least one ingredient.")
        self.assertFalse(Recipe.objects.filter(source="Custom").exists())

    def test_amount_must_be_more_than_0(self):
        response = self.client.post(reverse("recipes:create"), self.recipe_data([("Onion", "0")]))
        self.assertContains(response, "Amount must be more than 0.")
        self.assertFalse(Recipe.objects.filter(source="Custom").exists())

    def test_amount_needs_an_ingredient(self):
        response = self.client.post(reverse("recipes:create"), self.recipe_data([("Onion", "1"), ("", "5")]))
        self.assertContains(response, "Pick an ingredient for this amount.")
        self.assertFalse(Recipe.objects.filter(source="Custom").exists())

    def test_recipe_needs_a_name_and_instructions(self):
        data = self.recipe_data([("Onion", "1")], name="", instructions="")
        response = self.client.post(reverse("recipes:create"), data)
        self.assertTrue(response.context["form"].has_error("name"))
        self.assertTrue(response.context["form"].has_error("instructions"))
        self.assertFalse(Recipe.objects.filter(source="Custom").exists())

    def test_category_must_be_from_the_list(self):
        response = self.client.post(reverse("recipes:create"), self.recipe_data([("Onion", "1")], category="Pizza"))
        self.assertTrue(response.context["form"].has_error("category"))
        self.assertFalse(Recipe.objects.filter(source="Custom").exists())

    # ---------- who can see them ----------

    def test_custom_recipes_only_show_for_their_household(self):
        ours = self.make_recipe()
        theirs = self.make_recipe(household=self.other_household, created_by=self.other_user)

        response = self.client.get(reverse("recipes:index"))
        self.assertIn(ours, response.context["page"])
        self.assertNotIn(theirs, response.context["page"])

        # apple's recipe is a 404, the same as a recipe that doesn't exist
        self.assertEqual(self.client.get(reverse("recipes:detail", args=[theirs.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse("recipes:save", args=[theirs.id])).status_code, 404)

    def test_household_members_share_custom_recipes(self):
        # there's no join page yet, so apple joins banana's household directly
        HouseholdMember.objects.filter(user=self.other_user).update(household=self.household, role="member")
        recipe = self.make_recipe()

        self.client.login(username="apple", password="pass12345")
        response = self.client.get(reverse("recipes:index"), {"tab": "created"})
        self.assertEqual(list(response.context["page"]), [recipe])

        response = self.client.get(reverse("recipes:detail", args=[recipe.id]))
        self.assertContains(response, "Created by banana")

        # and apple can edit it, even though banana made it
        data = self.recipe_data([("Onion", "5")], initial_lines=1)
        self.client.post(reverse("recipes:edit", args=[recipe.id]), data)
        self.assertEqual(self.lines_of(recipe), [(self.onion, 5, True)])

    # ---------- created tab ----------

    def test_created_tab_only_shows_your_households_recipes(self):
        recipe = self.make_recipe()
        self.make_recipe(household=self.other_household, created_by=self.other_user)

        response = self.client.get(reverse("recipes:index"), {"tab": "created"})
        # not the TheMealDB curry, and not apple's recipe
        self.assertEqual(list(response.context["page"]), [recipe])
        self.assertEqual(response.context["created_count"], 1)
        self.assertContains(response, "Your recipe")

    def test_created_tab_with_nothing_created(self):
        response = self.client.get(reverse("recipes:index"), {"tab": "created"})
        self.assertContains(response, "You haven't created any recipes yet")

    # ---------- editing ----------

    def test_edit_page_starts_filled_in(self):
        recipe = self.make_recipe()
        response = self.client.get(reverse("recipes:edit", args=[recipe.id]))
        self.assertContains(response, 'value="Onion Soup"')
        self.assertContains(response, 'value="Onion"')
        # 3 instead of 3.0, so the amount box looks normal
        self.assertContains(response, 'value="3"')
        self.assertNotContains(response, 'value="3.0"')

    def test_edit_recipe(self):
        recipe = self.make_recipe()
        # change the name and the onions, and add some butter
        data = self.recipe_data([("Onion", "4"), ("Butter", "20")], initial_lines=1, name="Better Onion Soup")
        response = self.client.post(reverse("recipes:edit", args=[recipe.id]), data)
        self.assertRedirects(response, reverse("recipes:detail", args=[recipe.id]))

        recipe.refresh_from_db()
        self.assertEqual(recipe.name, "Better Onion Soup")
        self.assertEqual(self.lines_of(recipe), [(self.onion, 4, True), (self.butter, 20, True)])
        # still banana's household's recipe
        self.assertEqual(
            (recipe.source, recipe.household, recipe.created_by),
            ("Custom", self.household, self.user),
        )

    def test_removing_a_line(self):
        recipe = self.make_recipe()
        RecipeIngredient.objects.create(recipe=recipe, ingredient=self.butter, quantity=20)

        # the x button empties the line, and empty lines are left out
        data = self.recipe_data([("", ""), ("Butter", "20")], initial_lines=2)
        self.client.post(reverse("recipes:edit", args=[recipe.id]), data)
        self.assertEqual(self.lines_of(recipe), [(self.butter, 20, True)])

    def test_edit_with_a_mistake_changes_nothing(self):
        recipe = self.make_recipe()
        data = self.recipe_data([("Unicorn Tears", "1")], initial_lines=1, name="")
        response = self.client.post(reverse("recipes:edit", args=[recipe.id]), data)
        self.assertEqual(response.status_code, 200)

        recipe.refresh_from_db()
        self.assertEqual(recipe.name, "Onion Soup")
        self.assertEqual(self.lines_of(recipe), [(self.onion, 3, True)])

    def test_cant_edit_another_households_recipe(self):
        recipe = self.make_recipe(household=self.other_household, created_by=self.other_user)
        response = self.client.get(reverse("recipes:edit", args=[recipe.id]))
        self.assertEqual(response.status_code, 404)

        data = self.recipe_data([("Butter", "1")], initial_lines=1, name="Hacked")
        response = self.client.post(reverse("recipes:edit", args=[recipe.id]), data)
        self.assertEqual(response.status_code, 404)
        recipe.refresh_from_db()
        self.assertEqual(recipe.name, "Onion Soup")

    # ---------- deleting ----------

    def test_delete_recipe(self):
        recipe = self.make_recipe()
        SavedRecipe.objects.create(household=self.household, recipe=recipe, saved_by=self.user)

        response = self.client.post(reverse("recipes:delete", args=[recipe.id]))
        self.assertRedirects(response, reverse("recipes:index") + "?tab=created")
        # its lines and saves go with it
        self.assertFalse(Recipe.objects.filter(id=recipe.id).exists())
        self.assertFalse(RecipeIngredient.objects.filter(recipe_id=recipe.id).exists())
        self.assertFalse(SavedRecipe.objects.exists())

    def test_delete_needs_post(self):
        recipe = self.make_recipe()
        response = self.client.get(reverse("recipes:delete", args=[recipe.id]))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Recipe.objects.filter(id=recipe.id).exists())

    def test_cant_delete_another_households_recipe(self):
        recipe = self.make_recipe(household=self.other_household, created_by=self.other_user)
        response = self.client.post(reverse("recipes:delete", args=[recipe.id]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Recipe.objects.filter(id=recipe.id).exists())

    def test_themealdb_recipes_cant_be_edited_or_deleted(self):
        self.assertEqual(self.client.get(reverse("recipes:edit", args=[self.curry.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse("recipes:delete", args=[self.curry.id])).status_code, 404)
        self.assertTrue(Recipe.objects.filter(id=self.curry.id).exists())

    # ---------- people and households being deleted ----------

    def test_recipe_stays_when_the_person_who_made_it_is_deleted(self):
        kiwi = User.objects.create_user(username="kiwi", email="kiwi@example.com", password="pass12345")
        recipe = self.make_recipe(created_by=kiwi)
        kiwi.delete()
        recipe.refresh_from_db()
        self.assertIsNone(recipe.created_by)

        # the recipe page still works, it just can't say who made it any more
        response = self.client.get(reverse("recipes:detail", args=[recipe.id]))
        self.assertContains(response, "Created by someone in your household")

    def test_deleting_a_household_deletes_its_recipes(self):
        recipe = self.make_recipe(household=self.other_household, created_by=self.other_user)
        self.other_household.delete()
        self.assertFalse(Recipe.objects.filter(id=recipe.id).exists())
        self.assertFalse(RecipeIngredient.objects.filter(recipe_id=recipe.id).exists())
