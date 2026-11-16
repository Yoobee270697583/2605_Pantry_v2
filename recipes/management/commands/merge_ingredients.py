from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import ProtectedError
from recipes.models import Ingredient, IngredientAlias
from recipes.unit_helper import convert_to_ingredient_unit

# run with: python manage.py merge_ingredients
# TheMealDB lists some ingredients more than once under different names
# ("Onion", "Onions", "Yellow Onion"), so they show up as separate things when
# searching the pantry. for each duplicate in the list below this:
#   - moves its recipe lines onto the ingredient we keep, converting the
#     amounts into that ingredient's unit
#   - saves the duplicate's name as an alias, so the imports map it from now on
#   - deletes the duplicate
# no recipe ever gets removed - if an amount can't be converted, that line just
# stops being tracked (like a "pinch" line). safe to run again - anything
# already merged just gets skipped

# duplicate name -> the ingredient it gets merged into
# only things that are really the same thing in a pantry get merged. some look
# alike but are left alone on purpose, e.g. Ground Ginger (powder) vs Ginger
# (fresh root), Ground Coriander (seeds) vs Coriander (leaves), Red Pepper
# (capsicum) vs Black Pepper, Spring Onions vs Onion, Caster Sugar vs Sugar
INGREDIENT_ALIASES = {
    # onions
    "Onions": "Onion",
    "Yellow Onion": "Onion",
    "Chopped Onion": "Onion",
    "Scallions": "Spring Onions",

    # garlic
    "Garlic Clove": "Garlic",
    "Minced Garlic": "Garlic",
    "Garlic Granules": "Garlic Powder",

    # eggs
    "Eggs": "Egg",
    "Free-range Egg, Beaten": "Egg",
    "Free-range Eggs, Beaten": "Egg",

    # fruit and veg
    "Tomatoes": "Tomato",
    "Lemons": "Lemon",
    "Unwaxed Lemon": "Lemon",
    "Unwaxed Lime": "Lime",
    "Egg Plants": "Aubergine",
    "Zucchini": "Courgettes",
    "Frozen Peas": "Peas",

    # tinned tomatoes
    "Tinned Tomatos": "Chopped Tomatoes",
    "Canned Tomatoes": "Chopped Tomatoes",
    "Diced Tomatoes": "Chopped Tomatoes",

    # herbs and spices
    "Chopped Parsley": "Parsley",
    "Freshly Chopped Parsley": "Parsley",
    "Coriander Leaves": "Coriander",
    "Cilantro": "Coriander",
    "Cilantro Leaves": "Coriander",
    "Dried Oregano": "Oregano",
    "Pepper": "Black Pepper",
    "Ground Black Pepper": "Black Pepper",
    "Ground Cinnamon": "Cinnamon",
    "Ground Cumin": "Cumin",
    "Ground Nutmeg": "Nutmeg",
    "Ground Turmeric": "Turmeric",
    "Ground Allspice": "Allspice",
    "Chili Powder": "Chilli Powder",
    "Hot Chilli Powder": "Chilli Powder",
    "Red Chilli Powder": "Chilli Powder",
    "Red Chilli Flakes": "Chilli Flakes",
    "Red Pepper Flakes": "Chilli Flakes",

    # flour and sugar
    "Flour": "Plain Flour",
    "All purpose flour": "Plain Flour",
    "White Flour": "Plain Flour",
    "Strong white bread flour": "Bread Flour",
    "Strong White Flour": "Bread Flour",
    "Granulated Sugar": "Sugar",
    "Powdered Sugar": "Icing Sugar",
    "Dark Soft Brown Sugar": "Dark Brown Sugar",
    "Dark Brown Soft Sugar": "Dark Brown Sugar",

    # dairy
    "Salted Butter": "Butter",
    "Melted Butter": "Butter",
    "Chilled Butter": "Butter",
    "Whole Milk": "Milk",
    "Semi-skimmed Milk": "Milk",
    "Heavy Cream": "Double Cream",

    # meat and fish
    "Chicken Breasts": "Chicken Breast",
    "Ground Beef": "Minced Beef",
    "Lean Minced Beef": "Minced Beef",
    "Ground Pork": "Minced Pork",
    "Shrimp": "Prawns",
    "Raw Frozen Prawns": "Prawns",
    "Raw King Prawns": "King Prawns",
    "Raw tiger prawns": "Tiger Prawns",

    # everything else
    "Boiling Water": "Water",
    "Cold Water": "Water",
    "Warm Water": "Water",
    "Hot Beef Stock": "Beef Stock",
    "Unsalted Beef Stock": "Beef Stock",
    "Oil": "Vegetable Oil",
    "Extra Virgin Olive Oil": "Olive Oil",
    "Buns": "Bun",
}


class Command(BaseCommand):
    help = "Merges duplicate ingredients (e.g. Onions into Onion) and saves their names as aliases"

    def handle(self, *args, **options):
        merged = 0
        lines_moved = 0
        untracked_lines = []

        for duplicate_name, kept_name in INGREDIENT_ALIASES.items():
            kept = Ingredient.objects.filter(name__iexact=kept_name).first()
            if kept is None:
                self.stdout.write(self.style.WARNING(
                    f"no ingredient called '{kept_name}', run import_ingredients first"
                ))
                continue

            # save the alias even if the duplicate isn't in our table, so
            # import_ingredients never adds it back
            IngredientAlias.objects.get_or_create(
                name=duplicate_name,
                defaults={"ingredient": kept}
            )

            duplicate = Ingredient.objects.filter(name__iexact=duplicate_name).first()
            if duplicate is None:
                # already merged on an earlier run
                continue

            try:
                moved, untracked = self.merge(duplicate, kept)
            except ProtectedError:
                # something else (like a pantry item) still points at the duplicate
                self.stdout.write(self.style.WARNING(
                    f"couldnt merge {duplicate.name}, something else still uses it"
                ))
                continue

            merged += 1
            lines_moved += moved
            untracked_lines += untracked

        self.stdout.write(self.style.SUCCESS(
            f"merged {merged} duplicate ingredients, moved {lines_moved} recipe lines"
        ))
        if untracked_lines:
            self.stdout.write(f"{len(untracked_lines)} lines couldn't be converted, so they're kept but not tracked:")
            for line in untracked_lines:
                self.stdout.write(f"  {line}")

    def merge(self, duplicate, kept):
        """Moves the duplicate's recipe lines onto the kept ingredient, then deletes the duplicate.

        Returns (number of lines moved, descriptions of any lines that had to stop being tracked).
        """
        lines_moved = 0
        untracked_lines = []

        # atomic means if anything goes wrong, this merge gets undone completely
        with transaction.atomic():
            # nothing uses the kept ingredient yet, so it can just take the
            # duplicate's unit instead of every line needing converting
            if not kept.recipe_ingredients.exists():
                kept.unit = duplicate.unit
                kept.save()

            # copy the USDA weights across if only the duplicate has them
            if kept.fdc_id is None and duplicate.fdc_id is not None:
                kept.fdc_id = duplicate.fdc_id
                kept.grams_per_cup = duplicate.grams_per_cup
                kept.grams_per_tbsp = duplicate.grams_per_tbsp
                kept.grams_per_each = duplicate.grams_per_each
                kept.save()

            for line in duplicate.recipe_ingredients.select_related("recipe"):
                # the quantity is in the duplicate's unit, so convert it to the kept one
                if line.is_tracked and duplicate.unit != kept.unit:
                    quantity = convert_to_ingredient_unit(line.quantity, duplicate.unit, kept)

                    if quantity is None:
                        # can't convert it, so keep the line on the recipe but stop
                        # tracking it against the pantry - better than losing the recipe
                        line.quantity = None
                        line.is_tracked = False
                        untracked_lines.append(f"{line.recipe.name}: {line.measure_text} {duplicate.name}")
                    else:
                        line.quantity = quantity

                line.ingredient = kept
                line.save()
                lines_moved += 1

            duplicate.delete()

        return lines_moved, untracked_lines
