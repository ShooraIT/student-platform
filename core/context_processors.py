from .models import SiteSettings


def platform(request):
    ctx = {"site": SiteSettings.get()}
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        ctx["unread_count"] = user.notifications.filter(is_read=False).count()
        if user.is_student:
            from .levels import level_info

            ctx["level"] = level_info(user)
    return ctx
