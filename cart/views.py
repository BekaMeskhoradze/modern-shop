# cart/views.py
from django.db import transaction
from django.db.models import F
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from .models import Cart, CartItem
from core.models import Product, ProductSize


# ---------- Helpers ----------

def _get_or_create_cart(request):
    """
    აბრუნებს მიმდინარე სესიის კალათას.
    (იმუშავებს როგორც middleware-ის request.cart-ით, ისე მის გარეშე)
    """
    cart = getattr(request, "cart", None)
    if cart:
        return cart

    if not request.session.session_key:
        request.session.save()  # შექმნის session_key-ს

    cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key)
    return cart


def _cart_context(request):
    cart = _get_or_create_cart(request)
    items = cart.items.select_related("product", "product_size__size")
    return {"cart": cart, "items": items}


def _which_template(request) -> str:
    hx_target = request.headers.get("HX-Target", "")
    if hx_target == "cart-summary" or hx_target.startswith("cart-item-"):
        return "cart/cart_summary.html"
    return "cart/cart_modal.html"


def _recalculate(cart: Cart):
    if hasattr(cart, "recalculate") and callable(cart.recalculate):
        cart.recalculate()
        return
    if hasattr(cart, "update_totals") and callable(cart.update_totals):
        cart.update_totals()
        return

    # ფოლბექი
    try:
        items = cart.items.select_related("product")
        total_qty = sum(i.quantity for i in items)
        try:
            subtotal = sum(getattr(i, "total_price", i.product.price * i.quantity) for i in items)
        except Exception:
            subtotal = 0

        dirty_fields = []
        if hasattr(cart, "total_items"):
            cart.total_items = total_qty
            dirty_fields.append("total_items")
        if hasattr(cart, "subtotal"):
            cart.subtotal = subtotal
            dirty_fields.append("subtotal")
        if dirty_fields:
            cart.save(update_fields=dirty_fields)
    except Exception:
        # UI არ უნდა დაეგდოს
        pass


# ---------- Views ----------

class CartModalView(View):
    """Cart-ის გვერდითი მოდალი (HTMX)"""
    http_method_names = ["get"]

    def get(self, request):
        context = _cart_context(request)
        return render(request, "cart/cart_modal.html", context)


class CartCountView(View):
    """ბეჯის ქაუნთერი (JSON)"""
    http_method_names = ["get"]

    def get(self, request):
        cart = _get_or_create_cart(request)
        total = getattr(cart, "total_items", None)
        if total is None:
            total = sum(i.quantity for i in cart.items.all())
        return JsonResponse({"total_items": total})


class AddToCartView(View):
    """
    პროდუქტის დამატება კალათაში. POST: size_id (არასავალდებულო), quantity.
    """
    http_method_names = ["get", "post"]

    def get(self, request, slug):
        # პირდაპირ მისამართზე რომ არ დააგდოს 405 — გადავიყვანოთ პროდუქტზე
        product = get_object_or_404(Product, slug=slug)
        return redirect(product.get_absolute_url())

    def post(self, request, slug):
        cart = _get_or_create_cart(request)
        product = get_object_or_404(Product, slug=slug)

        # რაოდენობა (>=1)
        try:
            qty = int(request.POST.get("quantity", "1"))
        except ValueError:
            qty = 1
        qty = max(qty, 1)

        # ზომა — თუ გადმოვიდა, უნდა ეკუთვნოდეს ამავე პროდუქტს
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
                item.quantity = F("quantity") + qty
                item.save(update_fields=["quantity"])
                item.refresh_from_db(fields=["quantity"])
            else:
                CartItem.objects.create(
                    cart=cart,
                    product=product,
                    product_size=product_size,
                    quantity=qty,
                )

        _recalculate(cart)
        context = _cart_context(request)
        template = _which_template(request)
        return render(request, template, context)


class UpdateItemView(View):
    """qty inc/dec ან პირდაპირი რაოდენობის ცვლა"""
    http_method_names = ["get", "post"]

    def get(self, request, item_id):
        # Fallback 405-ის ნაცვლად
        return redirect("cart:summary")

    def post(self, request, item_id):
        cart = _get_or_create_cart(request)
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
        context = _cart_context(request)
        template = _which_template(request)
        return render(request, template, context)


class RemoveItemView(View):
    http_method_names = ["get", "post"]

    def get(self, request, item_id):
        return redirect("cart:summary")

    def post(self, request, item_id):
        cart = _get_or_create_cart(request)
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        item.delete()
        _recalculate(cart)

        context = _cart_context(request)
        template = _which_template(request)
        return render(request, template, context)


class ClearCartView(View):
    http_method_names = ["get", "post"]

    def get(self, request):
        return redirect("cart:summary")

    def post(self, request):
        cart = _get_or_create_cart(request)
        cart.items.all().delete()
        _recalculate(cart)

        context = _cart_context(request)
        template = _which_template(request)
        return render(request, template, context)


class CartSummaryView(TemplateView):
    """Cart-ის სრული გვერდი (/cart/)"""
    template_name = "cart/cart_summary.html"
    http_method_names = ["get"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cart = getattr(self.request, "cart", None)
        if cart is None:
            if not self.request.session.session_key:
                self.request.session.save()
            session_key = self.request.session.session_key
            cart, _ = Cart.objects.get_or_create(session_key=session_key)

        items = cart.items.select_related("product", "product_size__size")
        ctx.update({"cart": cart, "items": items})
        return ctx
