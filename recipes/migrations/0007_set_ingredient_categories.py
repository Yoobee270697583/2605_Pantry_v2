from django.db import migrations

from recipes.category_helper import guess_category

# fills in the new Ingredient.category for the ingredients that are already in
# the database (locally and on AWS), so nobody has to run anything extra -
# `migrate` does it. new ingredients get theirs from import_ingredients.
# the old categories people picked on their pantry items aren't copied over,
# because those are exactly the wrong ones (e.g. sirloin steak -> Drinks)


def set_categories(apps, schema_editor):
    Ingredient = apps.get_model("recipes", "Ingredient")
    for ingredient in Ingredient.objects.filter(category="other"):
        category = guess_category(ingredient.name)
        if category != "other":
            ingredient.category = category
            ingredient.save(update_fields=["category"])


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0006_ingredient_category"),
    ]

    operations = [
        # going backwards just leaves the categories as they are
        migrations.RunPython(set_categories, migrations.RunPython.noop),
    ]
