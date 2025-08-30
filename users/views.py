from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as DjangoLoginView, LogoutView as DjangoLogoutView
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView, FormView, UpdateView

from .forms import (
    CustomUserCreationForm,
    CustomUserLoginForm,
    CustomUserUpdateForm,
)
from .models import CustomUser
from core.models import Product


def hx_redirect(request, url_name: str, *args, **kwargs):
    url = reverse(url_name, args=args, kwargs=kwargs)
    if request.headers.get("HX-Request"):
        return HttpResponse(headers={"HX-Redirect": url})
    return None


# ------------ Register ------------
class RegisterView(FormView):
    template_name = "users/register.html"
    form_class = CustomUserCreationForm
    success_url = reverse_lazy("core:index")

    def form_valid(self, form):
        user = form.save()
        login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(self.request, "Registration successful.")
        resp = hx_redirect(self.request, "core:index")
        if resp:
            return resp
        return super().form_valid(form)


# ------------ Login ------------
class LoginView(DjangoLoginView):
    template_name = "users/login.html"
    authentication_form = CustomUserLoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, "Welcome back!")
        resp = hx_redirect(self.request, "core:index")
        if resp:
            return resp
        return super().form_valid(form)


# ------------ Logout ------------
class LogoutView(DjangoLogoutView):
    next_page = reverse_lazy("core:index")

    def dispatch(self, request, *args, **kwargs):
        # django LogoutView თვითონ აკეთებს logout-ს
        response = super().dispatch(request, *args, **kwargs)
        if request.headers.get("HX-Request"):
            return HttpResponse(headers={"HX-Redirect": reverse("core:index")})
        return response


# ------------ Profile page (full) ------------
class ProfileView(LoginRequiredMixin, TemplateView):
    login_url = "/users/login"
    template_name = "users/profile.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form"] = CustomUserUpdateForm(instance=self.request.user)
        ctx["user"] = self.request.user
        ctx["recomended_products"] = Product.objects.order_by("id")[:3]
        return ctx

    def post(self, request, *args, **kwargs):
        form = CustomUserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            resp = hx_redirect(request, "users:profile")
            if resp:
                return resp
            return TemplateResponse(request, self.template_name, self.get_context_data())
        ctx = self.get_context_data()
        ctx["form"] = form
        return TemplateResponse(request, self.template_name, ctx)


# ------------ Partials for HTMX ------------
class AccountDetailsPartialView(LoginRequiredMixin, TemplateView):
    login_url = "/users/login"
    template_name = "users/partials/account_details.html"

    def get_context_data(self, **kwargs):
        return {"user": self.request.user}


class EditAccountDetailsPartialView(LoginRequiredMixin, UpdateView):
    login_url = "/users/login"
    model = CustomUser
    form_class = CustomUserUpdateForm
    template_name = "users/partials/edit_account_details.html"

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        form.save()
        return TemplateResponse(
            self.request,
            "users/partials/account_details.html",
            {"user": self.request.user},
        )

    def form_invalid(self, form):
        return TemplateResponse(
            self.request,
            self.template_name,
            {"user": self.request.user, "form": form},
        )
