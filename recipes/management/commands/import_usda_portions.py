from django.core.management.base import BaseCommand
from recipes.models import Ingredient
from recipes.usda_helper import get_foods, get_portion_weights

# run with: python manage.py import_usda_portions
# saves USDA gram weights (per cup, tbsp and each) for the ingredients below,
# so import_recipes can convert things like "1 cup flour" when flour is stored
# in grams. run import_recipes again afterwards to pick up the extra recipes

# hand-picked USDA FoodData Central foods for the ingredients that block the
# most recipes. all SR Legacy foods since those have household portions.
# to add one, find its fdc id in the django shell with:
#   from recipes.usda_helper import search_foods
#   search_foods("butter")
USDA_INGREDIENTS = {
    # butter
    "Butter": 173410,               # Butter, salted
    "Melted Butter": 173410,        # Butter, salted
    "Unsalted Butter": 173430,      # Butter, without salt

    # sugar
    "Sugar": 169655,                # Sugars, granulated
    "Caster Sugar": 169655,         # Sugars, granulated
    "Brown Sugar": 168833,          # Sugars, brown
    "Icing Sugar": 169656,          # Sugars, powdered

    # flour
    "Flour": 168894,                # Wheat flour, white, all-purpose, enriched, bleached
    "Plain Flour": 168894,
    "All purpose flour": 168894,
    "Cornstarch": 169698,           # Cornstarch
    "Corn Flour": 169698,           # UK cornflour is the same as cornstarch

    # vegetables
    "Potatoes": 170026,             # Potatoes, flesh and skin, raw
    "Onion": 170000,                # Onions, raw
    "Garlic": 169230,               # Garlic, raw
    "Carrots": 170393,              # Carrots, raw
    "Tomato": 170457,               # Tomatoes, red, ripe, raw, year round average
    "Tomatoes": 170457,
    "Mushrooms": 169251,            # Mushrooms, white, raw
    "Spring Onions": 170005,        # Onions, spring or scallions, raw
    "Red Pepper": 170108,           # Peppers, sweet, red, raw
    "Ginger": 169231,               # Ginger root, raw
    "Peas": 170419,                 # Peas, green, raw
    "Sweetcorn": 169214,            # Corn, sweet, yellow, canned, whole kernel, drained solids

    # herbs and spices
    "Parsley": 170416,              # Parsley, fresh
    "Coriander": 169997,            # Coriander (cilantro) leaves, raw
    "Mint": 173475,                 # Spearmint, fresh
    "Cardamom": 170919,             # Spices, cardamom
    "Salt": 173468,                 # Salt, table

    # dairy
    "Milk": 171265,                 # Milk, whole, 3.25% milkfat
    "Greek Yogurt": 171284,         # Yogurt, plain, whole milk - USDA's greek yogurt has no cup weight
    "Mozzarella": 170845,           # Cheese, mozzarella, whole milk
    "Parmesan": 171247,             # Cheese, parmesan, grated
    "Condensed Milk": 171275,       # Milk, canned, condensed, sweetened
    "Coconut Milk": 170173,         # Nuts, coconut milk, canned

    # meat
    "Bacon": 168277,                # Pork, cured, bacon, unprepared
    "Chicken Thighs": 173627,       # Chicken, thigh, meat only, raw
    "Chicken Breast": 171077,       # Chicken, breast, skinless, boneless, raw

    # everything else
    "Rice": 168877,                 # Rice, white, long-grain, regular, raw
    "Breadcrumbs": 174928,          # Bread, crumbs, dry, grated, plain
    "Almonds": 170567,              # Nuts, almonds
    "Raisins": 168165,              # Raisins, dark, seedless
    "Yeast": 175043,                # Leavening agents, yeast, baker's, active dry
    "Tomato Puree": 170460,         # Tomato products, canned, puree
}


class Command(BaseCommand):
    help = "Saves USDA gram weights for common ingredients so more recipe amounts can be converted"

    def handle(self, *args, **options):
        # a few ingredients share a food, so only ask for each fdc id once
        fdc_ids = list(set(USDA_INGREDIENTS.values()))
        foods = get_foods(fdc_ids)

        if len(foods) == 0:
            self.stdout.write(self.style.ERROR("couldnt get any foods from USDA"))
            return

        # fdc id -> food, so we can look each one up below
        foods_by_id = {}
        for food in foods:
            foods_by_id[food["fdcId"]] = food

        updated = 0

        for name, fdc_id in USDA_INGREDIENTS.items():
            ingredient = Ingredient.objects.filter(name__iexact=name).first()
            if ingredient is None:
                self.stdout.write(self.style.WARNING(
                    f"no ingredient called '{name}', run import_ingredients first"
                ))
                continue

            food = foods_by_id.get(fdc_id)
            if food is None:
                self.stdout.write(self.style.WARNING(f"couldnt get USDA food {fdc_id} for {name}"))
                continue

            weights = get_portion_weights(food)

            ingredient.fdc_id = fdc_id
            ingredient.grams_per_cup = weights["grams_per_cup"]
            ingredient.grams_per_tbsp = weights["grams_per_tbsp"]
            ingredient.grams_per_each = weights["grams_per_each"]
            ingredient.save()
            updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"saved USDA weights for {updated} ingredients - run import_recipes again to pick up the recipes they unlock"
        ))
