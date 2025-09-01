from django.urls import path
from .views import (
    RegisterView, LoginView, LogoutView, ProfileView,
    AccountDetailsPartialView, EditAccountDetailsPartialView,
)

app_name = 'users'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/',    LoginView.as_view(),    name='login'),
    path('logout/',   LogoutView.as_view(),   name='logout'),

    path('profile/',  ProfileView.as_view(),  name='profile'),

    # HTMX partials
    path('account-details/',      AccountDetailsPartialView.as_view(),     name='account_details'),
    path('edit-account-details/', EditAccountDetailsPartialView.as_view(), name='edit_account_details'),
]
