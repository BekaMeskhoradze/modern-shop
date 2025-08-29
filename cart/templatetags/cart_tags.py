from django import template
from cart.models import Cart

register = template.Library()

@register.simple_tag(takes_context=True)
def get_cart_count(context):
    ctx_val = context.get("cart_total_items")
    if ctx_val is not None:
        return ctx_val

    request = context.get("request")
    if not request:
        return 0
    
    if not request.session.session_key:
        request.session.save()
    skey = request.session.session_key

    total = (
        Cart.objects
        .filter(session_key=skey)
        .values_list("total_items", flat=True)
        .first()
    )
    return total or 0


@register.filter
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
