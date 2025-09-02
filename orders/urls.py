from django.urls import path
from .views import CheckOutView, MyOrdersView, OrderDetailView

app_name = "orders"
urlpatterns = [
    path("checkout/", CheckOutView.as_view(), name="checkout"),
    path("my/", MyOrdersView.as_view(), name="my_orders"),
    path("<int:pk>/", OrderDetailView.as_view(), name="order_detail"),
]
