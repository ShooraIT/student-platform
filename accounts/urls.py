from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"
urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("mesh/login/", views.mesh_login, name="mesh_login"),
    path("mesh/callback/", views.mesh_callback, name="mesh_callback"),
    path("password/", views.password_change, name="password_change"),
]
