from .models import Cart

def cart_processor(request):
    cart = getattr(request, "cart", None)
    if not cart:
        if not request.session.session_key:
            request.session.create()
        cart_key = request.session.get("cart_key", request.session.session_key)
        cart, _ = Cart.objects.get_or_create(session_key=cart_key)

    return {
        "cart_total_items": cart.total_items,
        "cart_subtotal": cart.subtotal,
    }
