# core/views.py
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView, DetailView
from django.template.response import TemplateResponse
from django.db.models import Q, Prefetch, Min, Max
from django.core.cache import cache

from .models import Product, Category, Size, ProductImage, ProductSize
from .forms import ProductFilterForm

CATS_TTL = 60 * 10


# -----------------------------
# Helpers
# -----------------------------
def get_categories_cached():
    """
    კატეგორიების cache-ვა, რომ header-ში ყოველთვის ხელმისაწვდომი იყოს.
    """
    key = "core:categories:v1"
    cats = cache.get(key)
    if cats is None:
        cats = list(Category.objects.only("id", "name", "slug").order_by("name"))
        cache.set(key, cats, CATS_TTL)
    return cats


def apply_filters(qs, cleaned):
    """
    საერთო ჰელპერი: აპლაიებს ფორმით დავალიდებულ ფილტრებს queryset-ზე.
    """
    name = cleaned.get("name") or ""
    color = cleaned.get("color") or ""
    size = cleaned.get("size") or ""
    min_price = cleaned.get("min_price")
    max_price = cleaned.get("max_price")

    if name:
        qs = qs.filter(name__icontains=name)
    if color:
        qs = qs.filter(color__iexact=color)
    if size:
        qs = qs.filter(product_size__size__name__iexact=size).distinct()
    if min_price is not None:
        qs = qs.filter(price__gte=min_price)
    if max_price is not None:
        qs = qs.filter(price__lte=max_price)

    # sort
    sort = (cleaned.get("sort") or "").strip()
    if sort == "price_asc":
        qs = qs.order_by("price")
    elif sort == "price_desc":
        qs = qs.order_by("-price")
    elif sort == "newest":
        qs = qs.order_by("-created_at")
    # default relevance -> როგორცაა

    return qs


# -----------------------------
# Pages
# -----------------------------
class IndexView(TemplateView):
    template_name = "core/home_content.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = get_categories_cached()
        ctx["current_category"] = None
        ctx["search_query"] = self.request.GET.get("q", "")

        base_qs = (
            Product.objects.select_related("category")
            .only("id", "name", "slug", "price", "main_image", "created_at", "category_id")
        )
        latest = list(base_qs.order_by("-created_at")[:16])
        ctx["new_products"] = latest[:8]
        ctx["featured_products"] = latest[8:] or latest[:8]
        return ctx

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return TemplateResponse(request, self.template_name, context)


class CatalogView(TemplateView):
    template_name = "core/catalog.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        path_category_slug = self.kwargs.get("category_slug")
        categories = get_categories_cached()

        products = (
            Product.objects.select_related("category")
            .only("id", "name", "slug", "price", "color", "main_image", "created_at", "category_id")
            .order_by("-created_at")
        )
        form = ProductFilterForm(self.request.GET)
        form.is_valid()
        cd = form.cleaned_data

        current_category_obj = None
        current_category_slug = None
        query_category_slug = (cd.get("category") or "").strip()

        if query_category_slug:
            current_category_obj = get_object_or_404(
                Category.objects.only("id", "name", "slug"), slug=query_category_slug
            )
            products = products.filter(category=current_category_obj)
            current_category_slug = query_category_slug
        elif path_category_slug:
            current_category_obj = get_object_or_404(
                Category.objects.only("id", "name", "slug"), slug=path_category_slug
            )
            products = products.filter(category=current_category_obj)
            current_category_slug = path_category_slug

        products = apply_filters(products, cd)

        # UI ჩიფებისთვის პარამეტრები
        filter_params = {
            "category": query_category_slug,
            "name": cd.get("name") or "",
            "color": cd.get("color") or "",
            "size": cd.get("size") or "",
            "min_price": cd.get("min_price") if cd.get("min_price") is not None else "",
            "max_price": cd.get("max_price") if cd.get("max_price") is not None else "",
            "q": (self.request.GET.get("q") or "").strip(),
        }

        context.update(
            {
                "categories": categories,
                "products": products,
                "current_category": current_category_slug,
                "current_category_obj": current_category_obj,
                "filter_params": filter_params,
                "sizes": Size.objects.only("id", "name").order_by("name"),
                "search_query": "",
            }
        )
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if request.headers.get("HX-Request") and request.GET.get("show_filter"):
            return TemplateResponse(request, "core/includes/catalog_filters.html", context)
        return TemplateResponse(request, self.template_name, context)
class SearchView(TemplateView):
    """
    /search/?q=...&category=slug&size=M&color=Black&min_price=0&max_price=1000&sort=price_asc
    """
    template_name = "core/search_results.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        q = (self.request.GET.get("q") or "").strip()

        products = (
            Product.objects.select_related("category")
            .only("id", "name", "slug", "price", "color", "main_image", "created_at", "category_id")
        )

        # ტექსტური ძებნა
        if q:
            for term in q.split():
                products = products.filter(
                    Q(name__icontains=term)
                    | Q(description__icontains=term)
                    | Q(category__name__icontains=term)
                    | Q(color__icontains=term)
                )
            products = products.distinct()

        # ვალიდაცია/ფილტრები ProductFilterForm-ით
        form = ProductFilterForm(self.request.GET)
        form.is_valid()
        cd = form.cleaned_data

        # category (თუ მიეცა)
        category_slug = (cd.get("category") or "").strip()
        if category_slug:
            products = products.filter(category__slug=category_slug)

        # დანარჩენი ფილტრები + სორტი
        products = apply_filters(products, cd)

        # შაბლონისთვის დამატებითი მონაცემები (select options და არჩეული მნიშვნელობები)
        size = cd.get("size") or ""
        color = cd.get("color") or ""
        pmin = cd.get("min_price")
        pmax = cd.get("max_price")
        sort = cd.get("sort") or ""

        ctx.update(
            {
                "categories": get_categories_cached(),
                "current_category": category_slug or None,
                "search_query": q,
                "products": products,
                "sizes": Size.objects.only("id", "name").order_by("name"),
                "colors": (
                    Product.objects.exclude(color__isnull=True)
                    .exclude(color__exact="")
                    .values_list("color", flat=True)
                    .distinct()
                    .order_by("color")
                ),
                "price_range": Product.objects.aggregate(lo=Min("price"), hi=Max("price")),
                "selected_size": size,
                "selected_color": color,
                "price_min": pmin if pmin is not None else "",
                "price_max": pmax if pmax is not None else "",
                "sort": sort,
            }
        )
        return ctx


class ProductDetailView(DetailView):
    model = Product
    template_name = "core/product_detail.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return (
            Product.objects.select_related("category")
            .prefetch_related(
                Prefetch("images", queryset=ProductImage.objects.only("id", "image")),
                Prefetch(
                    "product_size",  # შეცვალე თუ related_name სხვაა
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
        ctx = super().get_context_data(**kwargs)
        product = self.object

        images = list(product.images.all())
        ps_all = list(product.product_size.all())  # შეცვალე თუ related_name სხვაა
        available_ps = [ps for ps in ps_all if ps.stock > 0]

        ctx.update(
            {
                "categories": get_categories_cached(),
                "current_category": product.category.slug,
                "gallery_images": images,
                "available_sizes": available_ps,
                "has_stock": bool(available_ps),
                "sizes_count": len(available_ps),
                "first_size": available_ps[0] if available_ps else None,
                "related_products": (
                    Product.objects.filter(category_id=product.category_id)
                    .exclude(id=product.id)
                    .only("id", "name", "slug", "main_image", "price", "category_id")
                    .prefetch_related(
                        Prefetch("images", queryset=ProductImage.objects.only("id", "image"))
                    )[:4]
                ),
            }
        )
        return ctx

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(**kwargs)
        return TemplateResponse(request, self.template_name, context)
