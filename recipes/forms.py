from django import forms

from .models import Recipe
from .unit_helper import convert_to_ingredient_unit
from .utils import find_ingredient

# the units someone can type a custom recipe amount in. whatever they pick is
# converted into the ingredient's own unit (g, ml or each) when it's saved -
# the same way the TheMealDB import turns "1/2 tsp" into ml - so the pantry
# still lines up, but the recipe can say "0.5 tsp" instead of "2.5 ml"
LINE_UNIT_CHOICES = [
    ("g", "g"),
    ("kg", "kg"),
    ("ml", "mL"),
    ("l", "L"),
    ("tsp", "tsp"),
    ("tbsp", "tbsp"),
    ("cup", "cup"),
    ("each", "each"),
]

# the units that always convert into each kind of ingredient, for the error message
SAME_KIND_UNITS = {
    "g": "g or kg",
    "ml": "mL, L, tsp, tbsp or cup",
    "each": "each",
}


class RecipeForm(forms.ModelForm):
    """The recipe's own details on the Create Recipe page. Its ingredient lines are a separate formset (below)."""

    # dropdowns instead of V1's free text, so custom recipes use the same
    # categories and cuisines as the TheMealDB ones and the filters stay tidy
    category = forms.ChoiceField(required=False, widget=forms.Select(attrs={"class": "form-select"}))
    area = forms.ChoiceField(required=False, widget=forms.Select(attrs={"class": "form-select"}))

    # optional - recipes without a picture show the Pantry icon instead.
    # assume_scheme adds https:// if someone pastes a link without it
    image_url = forms.URLField(
        required=False,
        max_length=500,
        assume_scheme="https",
        widget=forms.URLInput(attrs={"class": "form-control", "placeholder": "https://..."}),
    )

    class Meta:
        model = Recipe
        # is_private is the "Only my household can see this recipe" tick box
        fields = ["name", "category", "area", "image_url", "instructions", "is_private"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Grandma's Pasta"}),
            "instructions": forms.Textarea(attrs={"class": "form-control", "rows": 12, "placeholder": "Step 1: ..."}),
            "is_private": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # the options come from TheMealDB's recipes, the same as the filters on My Recipes
        mealdb_recipes = Recipe.objects.filter(household__isnull=True)
        categories = mealdb_recipes.exclude(category="").order_by("category").values_list("category", flat=True).distinct()
        areas = mealdb_recipes.exclude(area="").order_by("area").values_list("area", flat=True).distinct()

        self.fields["category"].choices = [("", "No category")] + [(category, category) for category in categories]
        self.fields["area"].choices = [("", "No cuisine")] + [(area, area) for area in areas]

        # blank=True on the model because some TheMealDB recipes don't have any,
        # but a custom recipe needs instructions (V1 made them required too)
        self.fields["instructions"].required = True


class IngredientLineForm(forms.Form):
    """One ingredient line on the Create Recipe page. Empty lines are ignored, so spare rows don't matter."""

    # typed in, with suggestions from our ingredient list. clean_ingredient turns
    # the name into the real Ingredient, so the line matches up with the pantry
    ingredient = forms.CharField(max_length=150, required=False)

    # in whatever unit is picked below. left empty for lines like "salt to taste"
    quantity = forms.FloatField(required=False)

    # starts on the ingredient's own unit (the page's script picks it), but can be
    # changed to e.g. tsp or cup. left empty, the ingredient's own unit is used
    unit = forms.ChoiceField(choices=[("", "Unit")] + LINE_UNIT_CHOICES, required=False)

    def clean_ingredient(self):
        name = self.cleaned_data["ingredient"]
        if not name:
            return None

        ingredient = find_ingredient(name)
        if ingredient is None:
            raise forms.ValidationError("Pick an ingredient from the list.")
        return ingredient

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if quantity is not None and quantity <= 0:
            raise forms.ValidationError("Amount must be more than 0.")
        return quantity

    def clean(self):
        cleaned_data = super().clean()

        ingredient = cleaned_data.get("ingredient")
        quantity = cleaned_data.get("quantity")

        # what gets saved: the amount in the ingredient's own unit, and the amount as
        # typed (e.g. "0.5 tsp") to show on the recipe. both empty for "salt to taste"
        cleaned_data["stored_quantity"] = None
        cleaned_data["measure_text"] = ""

        # an amount with nothing next to it is probably a mistake
        if quantity and "ingredient" in cleaned_data and ingredient is None:
            self.add_error("ingredient", "Pick an ingredient for this amount.")

        if ingredient and quantity:
            unit = cleaned_data.get("unit") or ingredient.unit
            unit_label = dict(LINE_UNIT_CHOICES)[unit]

            # e.g. 0.5 tsp of salt -> 2.5 ml. None if it can't be done, like cups of
            # something we have no USDA weight for
            converted = convert_to_ingredient_unit(quantity, unit, ingredient)

            if converted is None or converted <= 0:
                self.add_error(
                    "unit",
                    f"{ingredient.name} is measured in {ingredient.get_unit_display()}, and we can't convert "
                    f"{unit_label} into that. Use {SAME_KIND_UNITS[ingredient.unit]} instead.",
                )
            else:
                cleaned_data["stored_quantity"] = converted
                # only worth showing when it's not already in the ingredient's unit.
                # :g turns 0.5 into "0.5" and 2.0 into "2"
                if unit != ingredient.unit:
                    # "2 cups", but "1 cup" and "2 tsp"
                    if unit == "cup" and quantity != 1:
                        unit_label = "cups"
                    cleaned_data["measure_text"] = f"{quantity:g} {unit_label}"

        return cleaned_data


class BaseIngredientLineFormSet(forms.BaseFormSet):
    """Checks the lines together - a recipe needs at least one ingredient, and each ingredient only once."""

    def clean(self):
        # each line's own errors (like an ingredient we don't have) get shown first
        if any(self.errors):
            return

        ingredients = []
        for form in self.forms:
            ingredient = form.cleaned_data.get("ingredient")
            if ingredient is None:
                continue

            # one line per ingredient, like the pantry, so amounts never need adding together
            if ingredient in ingredients:
                raise forms.ValidationError(f"{ingredient.name} is on the list twice. Put the total amount on one line.")
            ingredients.append(ingredient)

        if len(ingredients) == 0:
            raise forms.ValidationError("Add at least one ingredient.")


# a formset is a list of the same small form, one per ingredient line.
# extra=3 starts the page with 3 empty lines, the "+ Add ingredient" button adds more
IngredientLineFormSet = forms.formset_factory(IngredientLineForm, formset=BaseIngredientLineFormSet, extra=3)
