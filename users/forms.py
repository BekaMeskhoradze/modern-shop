from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate, get_user_model
from django.core.validators import RegexValidator
from django.utils.html import strip_tags

User = get_user_model()

# --- Tailwind helpers (Modern Shop სტილი) ---
TW_INPUT_CLASSES  = "w-full px-3 py-2.5 rounded-xl border card focus:outline-none focus:ring-2"
TW_SELECT_CLASSES = "w-full px-3 py-2.5 rounded-xl border card focus:outline-none focus:ring-2"
TW_RING_STYLE     = {"style": "--tw-ring-color: rgba(245, 158, 11, 0.25)"}  # brand ring

def _merge_attrs(extra: dict | None = None) -> dict:
    base = {"class": TW_INPUT_CLASSES, **TW_RING_STYLE}
    return {**base, **(extra or {})}

def _password_widget(placeholder: str, autocomplete: str = "new-password"):
    return forms.PasswordInput(attrs=_merge_attrs({"placeholder": placeholder, "autocomplete": autocomplete}))

def _email_widget(placeholder: str = "Email"):
    return forms.EmailInput(attrs=_merge_attrs({"placeholder": placeholder, "autocomplete": "email"}))

def _text_widget(placeholder: str, autocomplete: str | None = None):
    attrs = {"placeholder": placeholder}
    if autocomplete:
        attrs["autocomplete"] = autocomplete
    return forms.TextInput(attrs=_merge_attrs(attrs))

def _select_widget():
    return forms.Select(attrs={"class": TW_SELECT_CLASSES, **TW_RING_STYLE})


# -------------------------------
# Registration
# -------------------------------
class CustomUserCreationForm(UserCreationForm):
    email      = forms.EmailField(required=True, max_length=254, widget=_email_widget())
    first_name = forms.CharField(required=True, max_length=50, widget=_text_widget("First Name", "given-name"))
    last_name  = forms.CharField(required=True, max_length=50, widget=_text_widget("Last Name", "family-name"))
    password1  = forms.CharField(required=True, widget=_password_widget("Password", "new-password"))
    password2  = forms.CharField(required=True, widget=_password_widget("Confirm password", "new-password"))

    class Meta:
        model  = User
        fields = ("first_name", "last_name", "email", "password1", "password2")

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email is already in use.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        if hasattr(user, "username") and not getattr(user, "username", None):
            try:
                user.username = (user.email or "").strip().lower()
            except Exception:
                pass
        if commit:
            user.save()
        return user


# -------------------------------
# Login (email as username UI)
# -------------------------------
class CustomUserLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Email",
        required=True,
        max_length=254,
        widget=_email_widget("Email"),
    )
    password = forms.CharField(
        label="Password",
        required=True,
        widget=_password_widget("Password", "current-password"),
    )

    def clean(self):
        email = (self.cleaned_data.get("username") or "").strip()
        password = self.cleaned_data.get("password")

        if email and password:
            # თუ გაქვს custom backend email-ით, ან username=email სტრატეგია
            self.user_cache = authenticate(self.request, username=email, password=password)
            if self.user_cache is None:
                raise forms.ValidationError("Invalid email or password.")
            if not self.user_cache.is_active:
                raise forms.ValidationError("This account is inactive.")
        return self.cleaned_data


# -------------------------------
# Profile update
# -------------------------------
class CustomUserUpdateForm(forms.ModelForm):
    phone = forms.CharField(
        required=False,
        max_length=150,
        validators=[RegexValidator(r'^\+?\d{9,15}$', message="Enter a valid phone number.")],
        widget=_text_widget("Phone", "tel"),
    )
    first_name = forms.CharField(required=True,  max_length=50, widget=_text_widget("First Name", "given-name"))
    last_name  = forms.CharField(required=True,  max_length=50, widget=_text_widget("Last Name", "family-name"))
    email      = forms.EmailField(required=False, max_length=254, widget=_email_widget("Email"))

    class Meta:
        model  = User
        fields = (
            "first_name", "last_name", "email",
            "company", "address1", "address2", "city", "country", "province", "postal_code", "phone"
        )
        widgets = {
            "company":     _text_widget("Company", "organization"),
            "address1":    _text_widget("Address Line 1", "address-line1"),
            "address2":    _text_widget("Address Line 2", "address-line2"),
            "city":        _text_widget("City", "address-level2"),
            "country":     _text_widget("Country", "country-name"),
            "province":    _text_widget("Province/State", "address-level1"),
            "postal_code": _text_widget("Postal Code", "postal-code"),
        }

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if email and User.objects.filter(email__iexact=email).exclude(id=self.instance.id).exists():
            raise forms.ValidationError("Email is already in use.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("email"):
            cleaned_data["email"] = (self.instance.email or "").strip().lower()

        for field in ["company", "address1", "address2", "city", "country", "province", "postal_code", "phone"]:
            if cleaned_data.get(field):
                cleaned_data[field] = strip_tags(str(cleaned_data[field])).strip()
        return cleaned_data
