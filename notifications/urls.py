from django.urls import path

from . import views

app_name = "notifications"
urlpatterns = [
    path("", views.index, name="index"),
    path("<int:pk>/", views.open_item, name="open"),
    path("read-all/", views.read_all, name="read_all"),
    path("settings/", views.settings_view, name="settings"),
    path("push/subscribe/", views.subscribe, name="subscribe"),
    path("push/resubscribe/", views.resubscribe, name="resubscribe"),
    path("push/unsubscribe/", views.unsubscribe, name="unsubscribe"),
    path("push/test/", views.test_push, name="test_push"),
    path("broadcast/", views.broadcast, name="broadcast"),
]
