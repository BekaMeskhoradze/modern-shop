from django.utils.deprecation import MiddlewareMixin
from .models import Cart

class CartMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not request.session.session_key:
            request.session.create()

        cart_key = request.session.setdefault("cart_key", request.session.session_key)

        cart, _ = Cart.objects.get_or_create(session_key=cart_key)

        request.cart = cart
        return None
