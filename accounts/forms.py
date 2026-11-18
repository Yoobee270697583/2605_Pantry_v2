from django import forms

from .models import User


class SignupForm(forms.Form):
    """Extra fields for allauth's signup page, so new accounts get a first and last name like V1."""

    # max_length matches the first_name and last_name columns on AbstractUser
    first_name = forms.CharField(max_length=150, label="First name")
    last_name = forms.CharField(max_length=150, label="Last name")

    def signup(self, request, user):
        # allauth calls this after it has created the user,
        # so we only need to add the names and save
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.save()


class NameForm(forms.ModelForm):
    """Your name on the Settings page. Your first name is what the rest of your household sees."""

    class Meta:
        model = User
        fields = ["first_name", "last_name"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # AbstractUser lets these be empty, but signup asks for both (SignupForm above), so this does too.
        # the form strips spaces first, so a name that's only spaces counts as empty
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True