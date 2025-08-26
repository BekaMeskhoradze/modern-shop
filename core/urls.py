# core/urls.py
from django.urls import path
from .views import IndexView, CatalogView, ProductDetailView, SearchView

app_name = "core"

urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("catalog/", CatalogView.as_view(), name="catalog_all"),
    path("catalog/<slug:category_slug>/", CatalogView.as_view(), name="catalog_category"),
    path("product/<slug:slug>/", ProductDetailView.as_view(), name="product_detail"),
    path("search/", SearchView.as_view(), name="search"),
]
