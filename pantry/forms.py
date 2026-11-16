from django import forms
from django.utils import timezone

from .models import PantryItem


class PantryItemForm(forms.ModelForm):
    """Used for both adding and editing a pantry item. The ingredient is picked
    from the Ingredients tab (add) or fixed (edit), so it isn't a form field."""

    class Meta:
        model = PantryItem
        fields = ["quantity", "category", "expiry_date"]
        widgets = {
            # step any lets people enter things like 1.5
            "quantity": forms.NumberInput(attrs={"class": "form-control", "step": "any", "min": "0"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            # type=date gives the browser's date picker
            "expiry_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # placeholder option instead of Django's default "---------"
        self.fields["category"].choices = [("", "Select a category")] + list(self.fields["category"].choices)[1:]
        # stops the date picker offering past dates - clean_expiry_date is the real check
        self.fields["expiry_date"].widget.attrs["min"] = timezone.localdate().isoformat()

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if quantity <= 0:
            raise forms.ValidationError("Quantity must be more than 0.")
        return quantity

    def clean_expiry_date(self):
        expiry_date = self.cleaned_data["expiry_date"]

        # an item that has already expired can still be edited (e.g. to change
        # the quantity), so only complain if the date is new or was changed
        is_unchanged = self.instance.pk and expiry_date == self.instance.expiry_date

        if expiry_date and expiry_date < timezone.localdate() and not is_unchanged:
            raise forms.ValidationError("Expiry date can't be in the past.")
        return expiry_date
