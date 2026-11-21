from django import forms
from .models import Client, Contact
from django.contrib.auth.forms import AuthenticationForm


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["name", "logo"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "logo": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ["client", "first_name", "surname", "email"]
        widgets = {
            "client": forms.Select(attrs={"class": "form-select"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "surname": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, client=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._fixed_client = client

        if client is not None:
            # Client is pre-bound from the URL — hide the dropdown
            self.fields.pop("client", None)
        else:
            # Standalone create form: model's blank=True makes the field
            # optional. Force it required + drop the empty option.
            self.fields["client"].required = True
            self.fields["client"].empty_label = None

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self._fixed_client is not None:
            obj.client = self._fixed_client
        if commit:
            obj.save()
        return obj

class StaffLoginForm(AuthenticationForm):
    """
    Extends Django's AuthenticationForm to:
      - Style the username/password widgets
      - Accept email OR username as the identifier
      - Reject non-staff users with a clear error
    """
    username = forms.CharField(
        label="Username or Email",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "you@example.com or username",
            "autofocus": True,
            "autocomplete": "username",
        }),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "••••••••",
            "autocomplete": "current-password",
        }),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        "not_staff": "This account does not have staff access.",
    }

    def clean(self):
        # Run Django's normal auth first (handles inactive, bad password, etc.)
        cleaned = super().clean()

        user = getattr(self, "user_cache", None)
        if user is not None and not user.is_staff:
            raise forms.ValidationError(
                self.error_messages["not_staff"],
                code="not_staff",
            )

        return cleaned
    