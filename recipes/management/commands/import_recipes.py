from collections import Counter
from django.core.management.base import BaseCommand
from django.db import transaction
from recipes.api_helper import search_recipes_by_letter, get_ingredients
from recipes.models import Ingredient, IngredientAlias, Recipe, RecipeIngredient
from recipes.grams_lists import STORE_IN_GRAMS
from recipes.unit_helper import parse_measure, to_base, convert_to_ingredient_unit

# run with: python manage.py import_recipes
# run import_ingredients and merge_ingredients first so the Ingredient table is filled.
# pulls every recipe from TheMealDB and converts each ingredient line into that
# ingredient's unit (g, ml or each). lines we can't convert, like "pinch", "1 bunch"
# or "1 cup" of something we only have in grams, still get saved, just not tracked.
# a recipe only gets skipped if it uses an ingredient that isn't in our list.
# safe to run again - recipes we already have get skipped

LETTERS = "abcdefghijklmnopqrstuvwxyz"


class Command(BaseCommand):
    help = "Imports recipes from TheMealDB, saving amounts we can't convert as not tracked"

    def handle(self, *args, **options):
        # lowercase name -> Ingredient, so "salt" and "Salt" both match
        ingredients = {}
        by_id = {}
        for ingredient in Ingredient.objects.all():
            ingredients[ingredient.name.lower()] = ingredient
            by_id[ingredient.id] = ingredient

        # merged names point at the ingredient they were merged into, e.g.
        # "onions" -> Onion (see merge_ingredients). uses the same Ingredient
        # object so a unit change below shows up under both names
        for alias in IngredientAlias.objects.all():
            ingredients[alias.name.lower()] = by_id[alias.ingredient_id]

        if len(ingredients) == 0:
            self.stdout.write(self.style.ERROR(
                "no ingredients yet, run python manage.py import_ingredients first"
            ))
            return

        # the free api has no "get all recipes" call so go through a-z
        meals = []
        for letter in LETTERS:
            meals += search_recipes_by_letter(letter)

        if len(meals) == 0:
            self.stdout.write(self.style.ERROR("couldnt get any recipes from TheMealDB"))
            return

        self.stdout.write(f"got {len(meals)} recipes from TheMealDB")

        self.set_ingredient_units(meals, ingredients)

        imported = 0
        already_had = 0
        skipped = Counter()

        for meal in meals:
            if Recipe.objects.filter(mealdb_id=meal["idMeal"]).exists():
                already_had += 1
                continue

            lines, problem = self.build_lines(meal, ingredients)
            if problem:
                skipped[problem] += 1
                continue

            self.save_recipe(meal, lines)
            imported += 1

        self.stdout.write(self.style.SUCCESS(
            f"imported {imported} new recipes, already had {already_had}"
        ))
        self.stdout.write(f"skipped {sum(skipped.values())} recipes:")
        for reason, count in skipped.most_common():
            self.stdout.write(f"  {count} - {reason}")

    def set_ingredient_units(self, meals, ingredients):
        """Picks the unit each ingredient is stored in - whichever kind (g, ml or each) the recipes use most.

        Only recipes that use the ingredient's own name count, so a merged name
        like "Flour" (mostly in cups) can't change what "Plain Flour" (mostly in
        grams) is stored in. If nothing uses its own name, its aliases decide.
        """
        # ingredient id -> Counter of how often each unit is used
        own_counts = {}
        alias_counts = {}

        for meal in meals:
            for item in get_ingredients(meal):
                key = item["name"].lower()
                quantity, unit = parse_measure(item["measure"])

                if key not in ingredients or unit is None or unit == "untracked":
                    continue

                ingredient = ingredients[key]

                # only need the unit here e.g. tbsp -> ml, kg -> g
                base_unit = to_base(quantity, unit)[1]

                # was it written with the ingredient's own name, or one of its aliases?
                if key == ingredient.name.lower():
                    counts = own_counts
                else:
                    counts = alias_counts

                if ingredient.id not in counts:
                    counts[ingredient.id] = Counter()
                counts[ingredient.id][base_unit] += 1

        # don't change the unit of an ingredient that recipes already use,
        # or their saved quantities would suddenly be in the wrong unit
        used_ids = set(RecipeIngredient.objects.values_list("ingredient_id", flat=True))

        for ingredient in set(ingredients.values()):
            counts = own_counts.get(ingredient.id) or alias_counts.get(ingredient.id)

            # dry goods like salt and cumin are measured in tsp, but bought by weight -
            # see recipes/grams_lists.py. only once they have a USDA weight,
            # or "1 tsp" couldn't be converted and those lines wouldn't be tracked
            has_weight = ingredient.grams_per_cup or ingredient.grams_per_tbsp
            if ingredient.name in STORE_IN_GRAMS and has_weight:
                best_unit = "g"
            elif counts:
                best_unit = counts.most_common(1)[0][0]
            else:
                continue

            if ingredient.id not in used_ids and ingredient.unit != best_unit:
                ingredient.unit = best_unit
                ingredient.save()

    def build_lines(self, meal, ingredients):
        """Turns a meal's ingredient list into lines ready to save.

        Returns (lines, problem). problem is None if the recipe is fine,
        otherwise it says why the recipe has to be skipped.
        """
        lines = []

        for item in get_ingredients(meal):
            ingredient = ingredients.get(item["name"].lower())
            if ingredient is None:
                return [], "uses an ingredient that isn't in our list"

            quantity, unit = parse_measure(item["measure"])

            # unit is "untracked" for things like "pinch" or "to taste",
            # and None for amounts we can't read like "1 bunch"
            converted = None
            if unit is not None and unit != "untracked":
                # None if it's in a different unit to the ingredient and there's no USDA weight for it
                converted = convert_to_ingredient_unit(quantity, unit, ingredient)

            # if it couldn't be converted, keep the line on the recipe page with its
            # original amount but don't track it, instead of skipping the whole recipe
            if converted is None:
                lines.append({
                    "ingredient": ingredient,
                    "quantity": None,
                    "is_tracked": False,
                    "measure_text": item["measure"][:100],
                })
            else:
                lines.append({
                    "ingredient": ingredient,
                    "quantity": converted,
                    "is_tracked": True,
                    "measure_text": item["measure"][:100],
                })

        return lines, None

    def save_recipe(self, meal, lines):
        """Saves the recipe and all its ingredient lines in one go."""
        # atomic means if anything fails halfway through, nothing gets saved
        with transaction.atomic():
            recipe = Recipe.objects.create(
                mealdb_id=meal["idMeal"],
                name=meal["strMeal"],
                category=meal.get("strCategory") or "",
                area=meal.get("strArea") or "",
                instructions=meal.get("strInstructions") or "",
                image_url=meal.get("strMealThumb") or "",
                youtube_url=meal.get("strYoutube") or "",
                source="TheMealDB",
            )

            for line in lines:
                RecipeIngredient.objects.create(
                    recipe=recipe,
                    ingredient=line["ingredient"],
                    quantity=line["quantity"],
                    is_tracked=line["is_tracked"],
                    measure_text=line["measure_text"],
                )
