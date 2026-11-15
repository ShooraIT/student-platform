from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """Студент с одноразовым паролем должен сменить его при первом входе."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and user.must_change_password:
            allowed = {reverse("accounts:password_change"), reverse("accounts:logout")}
            if request.path not in allowed and not request.path.startswith("/static/"):
                return redirect("accounts:password_change")
        return self.get_response(request)


# Префикс адреса -> раздел (см. User.can_access). Порядок важен: сначала более длинные префиксы.
SECTION_PREFIXES = [
    ("/career/employers/", "employers"),
    ("/career/mentor/", "mentor"),
    ("/career/meetings/", "mentor_meetings"),
    ("/career/", "career"),
    ("/tasks/", "tasks"),
    ("/surveys/", "surveys"),
    ("/shop/", "shop"),
    ("/profile/", "profile"),
    ("/rating/", "rating"),
]


class CourseAccessMiddleware:
    """Старшекурсникам доступны только мероприятия и портфолио; наставникам — ещё кабинет наставника и магазин."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            for prefix, section in SECTION_PREFIXES:
                if request.path.startswith(prefix):
                    if not user.can_access(section):
                        from django.contrib import messages

                        messages.info(request, "Этот раздел доступен первокурсникам")
                        return redirect("core:home")
                    break
        return self.get_response(request)
