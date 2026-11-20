from django import forms
from .models import Client, Contact


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
        # `client` is consumed here; it never reaches BaseModelForm.__init__
        super().__init__(*args, **kwargs)
        self._fixed_client = client
        if client is not None:
            # Client is pre-bound from the URL — hide the dropdown
            self.fields.pop("client", None)

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self._fixed_client is not None:
            obj.client = self._fixed_client
        if commit:
            obj.save()
        return obj



    