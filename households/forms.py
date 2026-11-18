from django import forms

from .models import Household


class JoinForm(forms.Form):
    """The "Got a code?" box. Dashes, spaces and lower case are fine - utils.clean_code tidies them."""
    code = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Enter invite code",
            "autocomplete": "off",
            "aria-label": "Invite code",
        }),
    )
    # only shown to people living alone. an unticked box isn't sent at all, so required=False
    bring_pantry = forms.BooleanField(
        required=False,
        initial=True,
        label="Bring my pantry and saved recipes with me",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class RenameForm(forms.ModelForm):
    class Meta:
        model = Household
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"class": "form-control", "aria-label": "Household name"})}

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Give your household a name.")
        return name
