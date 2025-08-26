# core/views.py
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView, DetailView
from django.template.response import TemplateResponse
from django.db.models import Q, Prefetch
from django.core.cache import cache

from .models import (
    Product,
    Category,
    Size,
    ProductImage,
    ProductSize,
)

# Categories cache TTL (10 minutes)
CATS_TTL = 60 * 10


def get_categories_cached():
    """Return categories list from cache (id, name, slug only)."""
    key = "core:categories:v1"
    cats = cache.get(key)
    if cats is None:
        cats = list(Category.objects.only("id", "name", "slug").order_by("name"))
        cache.set(key, cats, CATS_TTL)
    return cats


# ----------------------- Index -----------------------
class IndexView(TemplateView):
    """
    Home page: renders core/home_content.html which extends base.html.
    Works for both initial load and HTMX swaps (hx-select="#content").
    """
    template_name = "core/home_content.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = get_categories_cached()
        ctx["current_category"] = None
        ctx["search_query"] = self.request.GET.get("q", "")

        # Build light product datasets for the homepage
        base_qs = (
            Product.objects.select_related("category")
            .only("id", "name", "slug", "price", "main_image", "created_at", "category_id")
        )

        # Get up to 16 newest products and split into two sections
        latest = list(base_qs.order_by("-created_at")[:16])
        ctx["new_products"] = latest[:8]
        # If there aren't enough items for a separate featured list,
        # reuse the same slice so the section isn't empty.
        ctx["featured_products"] = latest[8:] or latest[:8]

        return ctx

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        # HTMX will extract #content automatically thanks to hx-select on <body>
        return TemplateResponse(request, self.template_name, context)


# ----------------------- Catalog (filters only) -----------------------
class CatalogView(TemplateView):
    template_name = "core/filter_results.html"

    FILTER_MAPPING = {
        "name":      lambda qs, v: qs.filter(name__icontains=v),   # NEW: product name
        "color":     lambda qs, v: qs.filter(color__iexact=v),
        "min_price": lambda qs, v: qs.filter(price__gte=v),
        "max_price": lambda qs, v: qs.filter(price__lte=v),
        "size":      lambda qs, v: qs.filter(product_size__size__name=v),
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # path category (optional)
        path_category_slug = self.kwargs.get("category_slug")
        # query category (from dropdown)
        query_category_slug = self.request.GET.get("category", "").strip()

        categories = get_categories_cached()

        products = (
            Product.objects.select_related("category")
            .only("id","name","slug","price","color","main_image","created_at","category_id")
            .order_by("-created_at")
        )
        current_category_obj = None
        current_category_slug = None

        # 1) dropdown category has priority
        if query_category_slug:
            current_category_obj = get_object_or_404(
                Category.objects.only("id","name","slug"), slug=query_category_slug
            )
            products = products.filter(category=current_category_obj)
            current_category_slug = query_category_slug
        # 2) else use path category
        elif path_category_slug:
            current_category_obj = get_object_or_404(
                Category.objects.only("id","name","slug"), slug=path_category_slug
            )
            products = products.filter(category=current_category_obj)
            current_category_slug = path_category_slug

        # filters (name, min/max, …)
        filter_params = {}
        for param, filter_func in self.FILTER_MAPPING.items():
            val = self.request.GET.get(param, "").strip()
            if val:
                products = filter_func(products, val)
                filter_params[param] = val
            else:
                filter_params[param] = ""

        # keep category value in filter_params for the dropdown state
        filter_params["category"] = query_category_slug

        context.update({
            "categories": categories,
            "products": products,
            "current_category": current_category_slug,
            "current_category_obj": current_category_obj,
            "filter_params": filter_params,
            "sizes": Size.objects.only("id", "name").order_by("name"),
            "search_query": "",
        })
        return context


# ----------------------- Search (text search only) -----------------------
class SearchView(TemplateView):
    """
    /search/?q=... — text search only.
    Splits query into words and searches across name, description, category name, color.
    """
    template_name = "core/search_results.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = (self.request.GET.get("q", "") or "").strip()

        products = (
            Product.objects.select_related("category")
            .only("id", "name", "slug", "price", "main_image", "created_at", "category_id")
            .order_by("-created_at")
        )

        if q:
            terms = q.split()  # e.g. "black jacket" -> ["black", "jacket"]

            # Require ALL terms to match in ANY of the fields (AND across terms, OR across fields)
            for term in terms:
                products = products.filter(
                    Q(name__icontains=term)
                    | Q(description__icontains=term)
                    | Q(category__name__icontains=term)
                    | Q(color__icontains=term)
                )

            products = products.distinct()
        else:
            # Empty query -> no results (ტემპლეიტი აჩვენებს ჰინტს)
            products = Product.objects.none()

        ctx.update({
            "categories": get_categories_cached(),
            "current_category": None,
            "search_query": q,
            "products": products,
        })
        return ctx



# ----------------------- Product detail -----------------------
class ProductDetailView(DetailView):
    model = Product
    template_name = "core/product_detail.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return (
            Product.objects.select_related("category")
            .prefetch_related(
                # extra images
                Prefetch(
                    "images",
                    queryset=ProductImage.objects.only("id", "image"),
                ),
                # sizes + stock
                Prefetch(
                    "product_size",
                    queryset=ProductSize.objects.select_related("size")
                    .only("id", "product_id", "stock", "size__name")
                    .order_by("size__name"),
                ),
            )
            .only(
                "id",
                "name",
                "slug",
                "price",
                "color",
                "description",
                "main_image",
                "category_id",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object

        context["categories"] = get_categories_cached()

        context["related_products"] = (
            Product.objects.filter(category_id=product.category_id)
            .exclude(id=product.id)
            .only("id", "name", "slug", "main_image", "price", "category_id")
            .prefetch_related(
                Prefetch("images", queryset=ProductImage.objects.only("id", "image"))
            )[:4]
        )

        context["current_category"] = product.category.slug
        # available sizes (if needed in template)
        context["sizes"] = [ps.size for ps in product.product_size.all() if ps.stock > 0]
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(**kwargs)

        if request.headers.get("HX-Request"):
            return TemplateResponse(request, "core/product_detail.html", context)

        return TemplateResponse(request, self.template_name, context)
