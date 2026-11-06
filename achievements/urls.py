from django.urls import path

from . import views

app_name = "achievements"
urlpatterns = [
    path("", views.rating, name="rating"),
    path("groups/", views.group_rating, name="groups"),
    path("badges/", views.achievements, name="list"),
]
