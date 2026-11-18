from django.core.management.base import BaseCommand
from recipes.api_helper import fetch_ingredient_list
from recipes.category_helper import guess_category
from recipes.models import Ingredient, IngredientAlias

# run with: python manage.py import_ingredients
# fills the Ingredient table with TheMealDB's ingredient list. safe to run
# again - ingredients we already have just get updated, not duplicated, and
# names that merge_ingredients merged into another ingredient are skipped


class Command(BaseCommand):
    help = "Imports TheMealDB's ingredient list into the Ingredient table"

    def handle(self, *args, **options):
        ingredients = fetch_ingredient_list()

        if len(ingredients) == 0:
            self.stdout.write(self.style.ERROR("couldnt get the ingredient list from TheMealDB"))
            return

        # names that have been merged into another ingredient (e.g. "Onions"),
        # so we don't add the duplicates back
        alias_names = set()
        for alias_name in IngredientAlias.objects.values_list("name", flat=True):
            alias_names.add(alias_name.lower())

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for item in ingredients:
            name = item["strIngredient"].strip()

            if name.lower() in alias_names:
                skipped_count += 1
                continue

            # only the name, id and image come from here - the unit gets
            # worked out by import_recipes, the USDA fields by the USDA import
            # and the category just below
            ingredient, created = Ingredient.objects.update_or_create(
                name=name,
                defaults={
                    "mealdb_id": item.get("idIngredient") or "",
                    "image_url": item.get("strThumb") or "",
                }
            )

            # TheMealDB doesn't give a category, so work one out from the name.
            # only for ingredients that don't have one yet, so a category
            # someone fixed in the admin isn't overwritten
            if ingredient.category == "other":
                category = guess_category(ingredient.name)
                if category != "other":
                    ingredient.category = category
                    ingredient.save(update_fields=["category"])

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"imported {created_count} new ingredients, updated {updated_count}, "
            f"skipped {skipped_count} merged duplicates"
        ))
