# cart/views.py
from django.db import transaction
from django.db.models import F
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import TemplateView

from .models import Cart, CartItem
from core.models import Product, ProductSize


# --------------------------
# Helpers
# --------------------------
def _recalculate(cart: Cart):
    """Recalculate totals safely (fallback if the model has no custom method)."""
    if hasattr(cart, "recalculate") and callable(cart.recalculate):
        cart.recalculate()
        return
    if hasattr(cart, "update_totals") and callable(cart.update_totals):
        cart.update_totals()
        return

    try:
        items = cart.items.select_related("product")
        total_qty = sum(i.quantity for i in items)
        try:
            subtotal = sum(getattr(i, "total_price", i.product.price * i.quantity) for i in items)
        except Exception:
            subtotal = 0

        dirty = []
        if hasattr(cart, "total_items"):
            cart.total_items = total_qty
            dirty.append("total_items")
        if hasattr(cart, "subtotal"):
            cart.subtotal = subtotal
            dirty.append("subtotal")
        if dirty:
            cart.save(update_fields=dirty)
    except Exception:
        # UI-ს არ ვაქცევინოთ erroრ
        pass


# --------------------------
# Cart mixin
# --------------------------
class CartMixin:
    """Reusable helpers for all cart views."""

    def get_cart(self, request):
        # თუ middleware-მა უკვე მიაბა, გამოვიყენოთ ის
        cart = getattr(request, "cart", None)
        if cart:
            return cart

        # შექმენი სესია უსაფრთხოდ (create() ძველს "ფლუშავს"; save() — არა)
        if not request.session.session_key:
            request.session.save()

        cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key)
        return cart

    def get_items(self, cart):
        return cart.items.select_related("product", "product_size__size")

    def pick_template(self, request) -> str:
        """
        If the target is the big container or specific row, return the full summary.
        Otherwise return the side modal template.
        """
        hx_target = request.headers.get("HX-Target", "") or ""
        if hx_target == "cart-summary" or hx_target.startswith("cart-item-"):
            return "cart/cart_summary.html"
        return "cart/cart_modal.html"

    def render_cart(self, request, context: dict | None = None, *, force_template: str | None = None):
        cart = self.get_cart(request)
        base = {"cart": cart, "items": self.get_items(cart)}
        if context:
            base.update(context)
        template = force_template or self.pick_template(request)
        return render(request, template, base)


# --------------------------
# Views
# --------------------------
class CartModalView(CartMixin, View):
    http_method_names = ["get"]

    def get(self, request):
        return self.render_cart(request, force_template="cart/cart_modal.html")


class CartCountView(CartMixin, View):
    http_method_names = ["get"]

    def get(self, request):
        cart = self.get_cart(request)
        total = getattr(cart, "total_items", None)
        if total is None:
            total = sum(i.quantity for i in cart.items.all())
        return JsonResponse({"total_items": total})


class AddToCartView(CartMixin, View):
    http_method_names = ["get", "post"]

    def get(self, request, slug):
        product = get_object_or_404(Product, slug=slug)
        return redirect(product.get_absolute_url())

    def post(self, request, slug):
        cart = self.get_cart(request)
        product = get_object_or_404(Product, slug=slug)

        # qty (>=1)
        try:
            qty = int(request.POST.get("quantity", "1"))
        except ValueError:
            qty = 1
        qty = max(qty, 1)

        # size (optional, უნდა ეკუთვნოდეს ამ პროდუქტს)
        size_id = request.POST.get("size_id")
        product_size = None
        if size_id:
            product_size = get_object_or_404(ProductSize.objects.filter(product=product), id=size_id)

        with transaction.atomic():
            qs = cart.items.select_for_update().filter(product=product)
            if product_size:
                qs = qs.filter(product_size=product_size)
            item = qs.first()

            if item:
                CartItem.objects.filter(id=item.id).update(quantity=F("quantity") + qty)
            else:
                CartItem.objects.create(
                    cart=cart, product=product, product_size=product_size, quantity=qty
                )

        _recalculate(cart)
        return self.render_cart(request)


class UpdateItemView(CartMixin, View):
    http_method_names = ["get", "post"]

    def get(self, request, item_id):
        return redirect("cart:summary")

    def post(self, request, item_id):
        cart = self.get_cart(request)
        item = get_object_or_404(CartItem, id=item_id, cart=cart)

        action = request.POST.get("action")
        with transaction.atomic():
            if action == "inc":
                CartItem.objects.filter(id=item.id).update(quantity=F("quantity") + 1)
            elif action == "dec":
                item.refresh_from_db(fields=["quantity"])
                if item.quantity <= 1:
                    item.delete()
                else:
                    CartItem.objects.filter(id=item.id).update(quantity=F("quantity") - 1)
            else:
                # quantity=...
                try:
                    q = int(request.POST.get("quantity", item.quantity))
                except ValueError:
                    q = item.quantity
                if q <= 0:
                    item.delete()
                else:
                    CartItem.objects.filter(id=item.id).update(quantity=q)

        _recalculate(cart)
        return self.render_cart(request)


class RemoveItemView(CartMixin, View):
    http_method_names = ["get", "post"]

    def get(self, request, item_id):
        return redirect("cart:summary")

    def post(self, request, item_id):
        cart = self.get_cart(request)
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        item.delete()
        _recalculate(cart)
        return self.render_cart(request)


class ClearCartView(CartMixin, View):
    http_method_names = ["get", "post"]

    def get(self, request):
        return redirect("cart:summary")

    def post(self, request):
        cart = self.get_cart(request)
        cart.items.all().delete()
        _recalculate(cart)
        return self.render_cart(request)


class CartSummaryView(CartMixin, TemplateView):
    template_name = "cart/cart_summary.html"
    http_method_names = ["get"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cart = self.get_cart(self.request)
        ctx.update({"cart": cart, "items": self.get_items(cart)})
        return ctx
