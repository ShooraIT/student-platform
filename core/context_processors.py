from .models import SiteSettings


def platform(request):
    ctx = {"site": SiteSettings.get()}
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        ctx["unread_count"] = user.notifications.filter(is_read=False).count()
    return ctx
