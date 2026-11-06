from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Степы — администрирование"
admin.site.site_title = "Степы"
admin.site.index_title = "Управление платформой"

from notifications.views import service_worker

urlpatterns = [
    path("sw.js", service_worker, name="service_worker"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("events/", include("events.urls")),
    path("tasks/", include("assignments.urls")),
    path("surveys/", include("surveys.urls")),
    path("shop/", include("shop.urls")),
    path("draws/", include("draws.urls")),
    path("rating/", include("achievements.urls")),
    path("notifications/", include("notifications.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
