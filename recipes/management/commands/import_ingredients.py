from django.core.management.base import BaseCommand
from recipes.api_helper import fetch_ingredient_list
from recipes.models import Ingredient

# run with: python manage.py import_ingredients
# fills the Ingredient table with TheMealDB's ingredient list. safe to run
# again - ingredients we already have just get updated, not duplicated


class Command(BaseCommand):
    help = "Imports TheMealDB's ingredient list into the Ingredient table"

    def handle(self, *args, **options):
        ingredients = fetch_ingredient_list()

        if len(ingredients) == 0:
            self.stdout.write(self.style.ERROR("couldnt get the ingredient list from TheMealDB"))
            return

        created_count = 0
        updated_count = 0

        for item in ingredients:
            name = item["strIngredient"].strip()

            # only the name, id and image come from here - the unit gets
            # worked out by import_recipes and the USDA fields by the USDA import
            ingredient, created = Ingredient.objects.update_or_create(
                name=name,
                defaults={
                    "mealdb_id": item.get("idIngredient") or "",
                    "image_url": item.get("strThumb") or "",
                }
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"imported {created_count} new ingredients, updated {updated_count}"
        ))
