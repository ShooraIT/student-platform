from django.urls import path

from . import views

app_name = "portfolio"
urlpatterns = [
    path("", views.portfolio, name="index"),
    path("add/", views.portfolio_add, name="add"),
    path("resume/", views.resume_edit, name="resume"),
    path("resume/print/", views.resume_print, name="print"),
    path("resume/new-link/", views.resume_token, name="token"),
]
