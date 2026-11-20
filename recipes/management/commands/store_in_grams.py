from django.core.management.base import BaseCommand
from django.db import transaction
from recipes.grams_lists import STORE_IN_GRAMS
from recipes.models import Ingredient, RecipeIngredient
from recipes.unit_helper import convert_to_ingredient_unit, parse_measure, to_grams

# 1. switches the ingredients in recipes/grams_lists.py (salt, cumin, flour...) from
#    ml or each to grams, and converts what uses them:
#    - recipe lines: "1 tsp cumin" is read again and converted into grams. one with
#      no weight to convert it (e.g. "1 packet" of pasta) is saved as not tracked
#    - pantry items: 120 ml of cumin becomes the same amount in grams. if a pantry
#      item can't be converted, that ingredient is left as it is, so nobody's
#      pantry ends up with the wrong amount
# 2. tries the recipes' other "not tracked" lines again. lines like "1 cup breadcrumbs"
#    were imported before breadcrumbs had a USDA weight, and the import never goes
#    back to recipes it already has - so they stayed not tracked



def amount_in_grams(quantity, ingredient):
    """Turns an amount in the ingredient's current unit (ml or each) into grams. None if there's no weight for it."""
    if ingredient.unit == "each":
        if ingredient.grams_per_each:
            return round(quantity * ingredient.grams_per_each, 2)
        return None

    grams = to_grams(quantity, ingredient.unit, ingredient)
    if grams is None:
        return None
    return round(grams, 2)


class Command(BaseCommand):
    help = "Stores dry goods like salt and cumin in grams instead of ml, and re-converts not tracked recipe lines"

    def handle(self, *args, **options):
        # atomic = everything gets converted, or nothing does
        with transaction.atomic():
            switched, untracked = self.switch_to_grams()
            tracked = self.track_lines_again()

        self.stdout.write(self.style.SUCCESS(
            f"switched {switched} ingredients to grams ({untracked} of their recipe lines had nothing to "
            f"convert with and aren't tracked now), and {tracked} other not tracked recipe lines are tracked now"
        ))

    def switch_to_grams(self):
        switched = 0
        untracked = 0

        for ingredient in Ingredient.objects.filter(name__in=STORE_IN_GRAMS).exclude(unit="g"):
            items = list(ingredient.pantry_items.all())

            # work out every pantry item's grams first, so nothing changes if one can't be done
            new_quantities = [amount_in_grams(item.quantity, ingredient) for item in items]
            if None in new_quantities:
                self.stdout.write(self.style.WARNING(
                    f"someone has {ingredient.name} in their pantry and there's no USDA weight to convert it "
                    f"- left in {ingredient.unit}"
                ))
                continue

            for item, quantity in zip(items, new_quantities):
                item.quantity = quantity
                # updated_at isn't listed, so it doesn't look like someone edited the item
                item.save(update_fields=["quantity"])

            lines = list(ingredient.recipe_ingredients.all())

            # custom recipe lines have no measure_text, so their amount is converted from
            # the old unit - done before the unit changes below
            custom_grams = {line.id: amount_in_grams(line.quantity, ingredient)
                            for line in lines if not line.measure_text and line.quantity is not None}

            ingredient.unit = "g"
            ingredient.save(update_fields=["unit"])

            for line in lines:
                if line.measure_text:
                    quantity, unit = parse_measure(line.measure_text)
                    # "pinch", "to taste" or something we can't read stays as it was
                    if quantity is None:
                        continue
                    grams = convert_to_ingredient_unit(quantity, unit, ingredient)
                elif line.quantity is not None:
                    grams = custom_grams[line.id]
                else:
                    # a custom line with no amount, e.g. salt to taste
                    continue

                if grams:
                    line.quantity = grams
                    line.is_tracked = True
                else:
                    if line.is_tracked:
                        untracked += 1
                    line.quantity = None
                    line.is_tracked = False
                line.save(update_fields=["quantity", "is_tracked"])

            switched += 1

        return switched, untracked

    def track_lines_again(self):
        tracked = 0

        # only lines with an amount written down - custom recipe lines left empty
        # (e.g. salt to taste) have nothing to convert
        lines = RecipeIngredient.objects.filter(is_tracked=False).exclude(measure_text="").select_related("ingredient")

        for line in lines:
            quantity, unit = parse_measure(line.measure_text)

            # "pinch", "to taste" or something we can't read, like "1 bunch"
            if quantity is None:
                continue

            converted = convert_to_ingredient_unit(quantity, unit, line.ingredient)
            if converted:
                line.quantity = converted
                line.is_tracked = True
                line.save(update_fields=["quantity", "is_tracked"])
                tracked += 1

        return tracked
