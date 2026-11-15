from django import forms


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