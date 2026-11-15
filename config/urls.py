from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "01:17 — администрирование"
admin.site.site_title = "01:17"
admin.site.index_title = "Управление платформой"

from career.views import public_portfolio
from notifications.views import service_worker

urlpatterns = [
    path("sw.js", service_worker, name="service_worker"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("events/", include("events.urls")),
    path("tasks/", include("assignments.urls")),
    path("surveys/", include("surveys.urls")),
    path("shop/", include("shop.urls")),
    path("rating/", include("achievements.urls")),
    path("notifications/", include("notifications.urls")),
    path("career/", include("career.urls")),
    path("portfolio/", include("career.portfolio_urls")),
    path("p/<str:token>/", public_portfolio, name="public_portfolio"),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
