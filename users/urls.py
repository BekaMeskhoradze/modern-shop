from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('account-details/', views.AccountDetailsView.as_view(), name='account_details'),
    path('edid-account-details/', views.EditAccountDetailsView.as_view(), name='edit_account_details'),
    path('update-account-details/', views.UpdateAccountDetailsView.as_view(), name='update_account_details'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
]

