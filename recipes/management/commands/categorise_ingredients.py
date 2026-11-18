from django.core.management.base import BaseCommand
from recipes.category_helper import guess_category
from recipes.models import Ingredient

# run with: python manage.py categorise_ingredients
# works out the pantry category (Fruit & Vegetables, Meat & Seafood...) for
# ingredients that are still "Other". import_ingredients and the migration
# already do this - run it again after adding words to category_helper.py.



class Command(BaseCommand):
    help = "Sets each ingredient's pantry category from its name"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="recategorise every ingredient, overwriting categories fixed in the admin",
        )

    def handle(self, *args, **options):
        ingredients = Ingredient.objects.all()
        if not options["all"]:
            ingredients = ingredients.filter(category="other")

        changed = 0
        for ingredient in ingredients:
            category = guess_category(ingredient.name)
            if category != ingredient.category:
                ingredient.category = category
                ingredient.save(update_fields=["category"])
                changed += 1

        still_other = Ingredient.objects.filter(category="other").count()
        self.stdout.write(self.style.SUCCESS(
            f"updated {changed} ingredients - {still_other} are still 'Other' "
            f"(These can be fixed in the admin, or we canadd words to the recipes/category_helper.py)"
        ))
