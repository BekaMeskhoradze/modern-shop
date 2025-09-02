# orders/views.py
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView, DetailView

from .forms import OrderForm
from .models import Order, OrderItem
from cart.views import CartMixin
from payment.views import create_stripe_checkout_session


def _is_htmx_partial(request) -> bool:
    hx = request.headers.get("HX-Request")
    boosted = request.headers.get("HX-Boosted")
    return bool(hx) and not bool(boosted)


@method_decorator(login_required(login_url="/users/login"), name="dispatch")
class CheckOutView(CartMixin, View):
    def get(self, request):
        cart = self.get_cart(request)

        if cart.total_items == 0:
            if _is_htmx_partial(request):
                return TemplateResponse(
                    request,
                    "orders/empty_cart.html",
                    {
                        "message": "Your cart is empty. Please add items to your cart before proceeding to checkout."
                    },
                )
            return redirect("cart:summary")

        context = {
            "form": OrderForm(user=request.user),
            "cart": cart,
            "cart_items": cart.items.select_related("product", "product_size__size").order_by("-added_at"),
            "total_price": cart.subtotal,
        }

        if _is_htmx_partial(request):
            return TemplateResponse(request, "orders/checkout_content.html", context)

        return render(request, "orders/checkout.html", context)

    def post(self, request):
        cart = self.get_cart(request)
        payment_provider = request.POST.get("payment_provider")

        if cart.total_items == 0:
            if _is_htmx_partial(request):
                return TemplateResponse(
                    request,
                    "orders/empty_cart.html",
                    {
                        "message": "Your cart is empty. Please add items to your cart before proceeding to checkout."
                    },
                )
            return redirect("cart:summary")

        if not payment_provider or payment_provider not in ["stripe", "heleket"]:
            context = {
                "form": OrderForm(user=request.user),
                "cart": cart,
                "cart_items": cart.items.select_related("product", "product_size__size").order_by("-added_at"),
                "total_price": cart.subtotal,
                "error_message": "Please select a valid payment method (Stripe or Heleket).",
            }
            if _is_htmx_partial(request):
                return TemplateResponse(request, "orders/checkout_content.html", context)
            return render(request, "orders/checkout.html", context)

        total_price = cart.subtotal
        form_data = request.POST.copy()
        if not form_data.get("email"):
            form_data["email"] = request.user.email
        form = OrderForm(form_data, user=request.user)

        if form.is_valid():
            order = Order.objects.create(
                user=request.user,
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                email=form.cleaned_data["email"],
                company=form.cleaned_data.get("company"),
                address1=form.cleaned_data.get("address1"),
                address2=form.cleaned_data.get("address2"),
                city=form.cleaned_data.get("city"),
                country=form.cleaned_data.get("country"),
                province=form.cleaned_data.get("province"),
                postal_code=form.cleaned_data.get("postal_code"),
                phone=form.cleaned_data.get("phone"),
                special_instructions="",
                total_price=total_price,
                payment_provider=payment_provider,
            )

            for item in cart.items.select_related("product", "product_size__size"):
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    size=item.product_size,
                    quantity=item.quantity,
                    price=item.product.price or Decimal("0.00"),
                )

            # Stripe checkout
            try:
                if payment_provider == "stripe":
                    checkout_session = create_stripe_checkout_session(order, request)
                    if request.headers.get("HX-Request"):
                        # HTMX redirect
                        resp = HttpResponse(status=200)
                        resp["HX-Redirect"] = checkout_session.url
                        return resp
                    return redirect(checkout_session.url)
            except Exception as e:
                order.delete()
                context = {
                    "form": form,
                    "cart": cart,
                    "cart_items": cart.items.select_related("product", "product_size__size").order_by("-added_at"),
                    "total_price": total_price,
                    "error_message": f"An error occurred while processing your payment: {str(e)}. Please try again.",
                }
                if _is_htmx_partial(request):
                    return TemplateResponse(request, "orders/checkout_content.html", context)
                return render(request, "orders/checkout.html", context)

        context = {
            "form": form,
            "cart": cart,
            "cart_items": cart.items.select_related("product", "product_size__size").order_by("-added_at"),
            "total_price": total_price,
            "error_message": "There were errors in your form. Please correct them and try again.",
        }
        if _is_htmx_partial(request):
            return TemplateResponse(request, "orders/checkout_content.html", context)
        return render(request, "orders/checkout.html", context)


# -----------------------------
# My Orders + Order detail
# -----------------------------
class MyOrdersView(LoginRequiredMixin, ListView):
    template_name = "orders/my_orders.html"
    context_object_name = "orders"
    paginate_by = 10

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .prefetch_related("items__product", "items__size__size")
            .order_by("-created_at")
        )


class OrderDetailView(LoginRequiredMixin, DetailView):
    model = Order
    template_name = "orders/order_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(user=self.request.user)
            .prefetch_related("items__product", "items__size__size")
        )
