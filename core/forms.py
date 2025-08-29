# core/forms.py
from django import forms

class ProductFilterForm(forms.Form):
    category   = forms.SlugField(required=False)
    name       = forms.CharField(required=False)
    color      = forms.CharField(required=False)
    size       = forms.CharField(required=False)
    min_price  = forms.DecimalField(required=False, min_value=0)
    max_price  = forms.DecimalField(required=False, min_value=0)
    sort       = forms.ChoiceField(
        required=False,
        choices=[("price_asc","Price ↑"),("price_desc","Price ↓"),("newest","Newest")]
    )
