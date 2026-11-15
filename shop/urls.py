from django.urls import path

from . import views

app_name = "shop"
urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("<int:pk>/", views.product_detail, name="product"),
    path("<int:pk>/buy/", views.buy, name="buy"),
    path("orders/<int:pk>/", views.order_detail, name="order"),
    path("orders/<int:pk>/cancel/", views.order_cancel, name="order_cancel"),
    path("issue/", views.issue, name="issue"),
    path("award/", views.award, name="award"),
]
