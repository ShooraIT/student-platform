from django.urls import path

from . import views

app_name = "draws"
urlpatterns = [
    path("", views.draw_list, name="list"),
    path("<int:pk>/", views.draw_detail, name="detail"),
    path("<int:pk>/enter/", views.enter, name="enter"),
    path("<int:pk>/staff/", views.staff, name="staff"),
]
