# cart/forms.py
from django import forms
from core.models import ProductSize

class AddToCartForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, initial=1)

    def __init__(self, *args, product=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.product = product
        # ვიღებთ ამ პროდუქტის ზომებს, რომლებსაც აქციაში აქვს მარაგი
        sizes_qs = (
            ProductSize.objects.select_related("size")
            .filter(product=product, stock__gt=0)
            if product else ProductSize.objects.none()
        )
        if sizes_qs.exists():
            self.fields["size_id"] = forms.TypedChoiceField(
                choices=[(ps.id, ps.size.name) for ps in sizes_qs],
                coerce=int,
                required=True,
                initial=sizes_qs.first().id,
            )