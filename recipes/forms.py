from django import forms

from .models import Recipe
from .utils import find_ingredient


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

    # in the ingredient's own unit (g, ml or each), the same as pantry items.
    # left empty for lines like "salt to taste"
    quantity = forms.FloatField(required=False)

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

        # an amount with nothing next to it is probably a mistake
        if cleaned_data.get("quantity") and "ingredient" in cleaned_data and cleaned_data["ingredient"] is None:
            self.add_error("ingredient", "Pick an ingredient for this amount.")
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
