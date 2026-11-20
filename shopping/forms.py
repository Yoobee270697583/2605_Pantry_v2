from django import forms

# the most that can be added in one go - 100 kg, 100 L or 100,000 of something. nobody buys that much,
# it's here so a slip of the finger (or someone typing 1e300) can't put a silly number on the list
MAX_AMOUNT = 100000


class AmountForm(forms.Form):
    """The amount box next to an ingredient on the Shopping List page.

    The ingredient isn't a field - it comes from the button that was pressed (its id is in the URL),
    the same as PantryItemForm. This only checks the amount is a sensible number above zero.
    """
    quantity = forms.FloatField(error_messages={
        "required": "Enter an amount.",
        "invalid": "Enter a number for the amount.",
    })

    def clean_quantity(self):
        # 2 decimal places, like every other amount. it's rounded before the checks, so 0.001 (which
        # rounds to 0) gets the message below instead of breaking the database's above-zero rule
        quantity = round(self.cleaned_data["quantity"], 2)
        if quantity <= 0:
            raise forms.ValidationError("Enter an amount more than 0.")
        if quantity > MAX_AMOUNT:
            raise forms.ValidationError("That's too much. Enter an amount of 100,000 or less.")
        return quantity
