from django.urls import path
from .views import (
    CartModalView, CartCountView, AddToCartView, CartSummaryView,
    UpdateItemView, RemoveItemView, ClearCartView,
)

app_name = "cart"

urlpatterns = [
    path("modal/", CartModalView.as_view(), name="cart_modal"),
    path("count/", CartCountView.as_view(), name="cart_count"),
    path("add/<slug:slug>/", AddToCartView.as_view(), name="add_to_cart"),
    path("update/<int:item_id>/", UpdateItemView.as_view(), name="update_item"),
    path("remove/<int:item_id>/", RemoveItemView.as_view(), name="remove_item"),
    path("clear/", ClearCartView.as_view(), name="clear"),
    path("", CartSummaryView.as_view(), name="summary"),
]
