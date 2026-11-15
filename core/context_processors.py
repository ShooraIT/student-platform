from .models import SiteSettings


def platform(request):
    ctx = {"site": SiteSettings.get()}
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        ctx["unread_count"] = user.notifications.filter(is_read=False).count()
        ctx["section_access"] = {
            "tasks": user.can_access("tasks"),
            "surveys": user.can_access("surveys"),
            "career": user.can_access("career"),
            "mentor": user.can_access("mentor"),
            "mentor_meetings": user.can_access("mentor_meetings"),
            "employers": user.can_access("employers"),
            "shop": user.can_access("shop"),
            "rating": user.can_access("rating"),
        }
    return ctx
