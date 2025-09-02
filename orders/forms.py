from django import forms
from django.utils.html import strip_tags

BASE_INPUT_CLASS = (
    "w-full rounded-xl border card px-3 py-2 text-sm "
    "focus:outline-none focus:ring-2"
)
ERROR_CLASS = "border-red-400 ring-1 ring-red-300"

class OrderForm(forms.Form):
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            "placeholder": "First Name",
        }),
    )
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            "placeholder": "Last Name",
        }),
    )
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={
            "placeholder": "Email",
        }),
    )
    company = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "Company (Optional)",
        }),
    )
    address1 = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "Address Line 1 (Optional)",
        }),
    )
    address2 = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "Address Line 2 (Optional)",
        }),
    )
    city = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "City (Optional)",
        }),
    )
    country = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "Country (Optional)",
        }),
    )
    province = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "Province/State (Optional)",
        }),
    )
    postal_code = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "Postal Code (Optional)",
        }),
    )
    phone = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "Phone Number (Optional)",
        }),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user:
            self.fields["first_name"].initial = getattr(user, "first_name", "")
            self.fields["last_name"].initial  = getattr(user, "last_name", "")
            self.fields["email"].initial      = getattr(user, "email", "")
            self.fields["company"].initial    = getattr(user, "company", "")
            self.fields["address1"].initial   = getattr(user, "address1", "")
            self.fields["address2"].initial   = getattr(user, "address2", "")
            self.fields["city"].initial       = getattr(user, "city", "")
            self.fields["country"].initial    = getattr(user, "country", "")
            self.fields["province"].initial   = getattr(user, "province", "")
            self.fields["postal_code"].initial= getattr(user, "postal_code", "")
            self.fields["phone"].initial      = getattr(user, "phone", "")

        # ერთიანი ვიზუალი base.html-ის თემაზე
        for name, field in self.fields.items():
            w = field.widget
            w.attrs["class"] = BASE_INPUT_CLASS
            # accent ფერის რგოლი (იგივე, რაც Search input-ს აქვს header-ში)
            prev_style = w.attrs.get("style", "")
            w.attrs["style"] = (prev_style + " --tw-ring-color: rgba(245, 158, 11, 0.25);").strip()
            if self.is_bound and name in self.errors:
                w.attrs["class"] += " " + ERROR_CLASS

        auto = {
            "first_name": "given-name",
            "last_name": "family-name",
            "email": "email",
            "address1": "address-line1",
            "address2": "address-line2",
            "city": "address-level2",
            "province": "address-level1",
            "postal_code": "postal-code",
            "country": "country-name",
            "phone": "tel",
        }
        for name, val in auto.items():
            if name in self.fields:
                self.fields[name].widget.attrs["autocomplete"] = val

        self.fields["phone"].widget.attrs.update({"type": "tel", "inputmode": "tel"})
        if not self.is_bound:
            self.fields["first_name"].widget.attrs["autofocus"] = "autofocus"

    def clean(self):
        cleaned_data = super().clean()
        for field in ["company", "address1", "address2", "city", "country", "province", "postal_code", "phone"]:
            val = cleaned_data.get(field)
            if val:
                val = strip_tags(val).strip()
                cleaned_data[field] = val
        return cleaned_data
