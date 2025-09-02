import stat
from django.shortcuts import render
import stripe
import requests
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed
from django.template.response import TemplateResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from orders.models import Order
from cart.views import CartMixin
from decimal import ROUND_HALF_UP, Decimal
import json
import hashlib
import base64

# stripe login
# stripe listen --forward-to localhost:8000/payment/stripe/webhook/

stripe.api_key = settings.STRIPE_SECRET_KEY
stripe_endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

def create_stripe_checkout_session(order, request):
    line_items = []
    for oi in order.items.select_related('product', 'size__size'):
        unit_amount = int((oi.price * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        line_items.append({
            'price_data': {
                'currency': 'eur', # Adjust currency as needed
                'product_data': {
                    'name': f'{oi.product.name} - {oi.size.size.name}',
                },
                'unit_amount': unit_amount,
            },
            'quantity': oi.quantity,
        })
    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=line_items,
        mode='payment',
        success_url=request.build_absolute_uri('/payment/stripe/success/') + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=request.build_absolute_uri('/payment/stripe/cancel/') + f'?order_id={order.id}',
        metadata={'order_id': order.id},
    )

    order.stripe_payment_intent_id = checkout_session.payment_intent
    order.payment_provider = 'stripe'
    order.save(update_fields=['stripe_payment_intent_id', 'payment_provider'])
    return checkout_session


@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event=None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, stripe_endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return HttpResponse(status=400)
    
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        order_id = session['metadata'].get('order_id')

        try:
            order = Order.objects.get(id=order_id)
            order.status = 'processing'
            order.stripe_payment_intent_id = session.get('payment_intent')
            order.save()
        except Order.DoesNotExist:
            return HttpResponse(status=400)
        
    return HttpResponse(status=200)

def stripe_success(request):
    session_id = request.GET.get('session_id')
    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            order_id = session.metadata.get('order_id')
            order = get_object_or_404(Order, id=order_id)

            cart = CartMixin().get_cart(request)
            cart.clear()

            context = {'order': order}
            if request.headers.get('HX-Request'):
                return TemplateResponse(request, 'payment/stripe_success_partial.html', context)
            return render(request, 'payment/stripe_success.html', context)
        except Exception as e:
            raise
    return redirect('core:index')

def stripe_cancel(request):
    order_id = request.GET.get('order_id')
    if order_id:
        order = get_object_or_404(Order, id=order_id)
        order.status = 'canceled'
        order.save()
        context = {'order': order}
        if request.headers.get('HX-Request'):
            return TemplateResponse(request, 'payment/stripe_cancel_content.html', context)
        return render(request, 'payment/stripe_cancel.html', context)
    return redirect('orders:checkout')