from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.models import AuditLog

from . import mesh


class LoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.is_student and not settings.STUDENT_PASSWORD_LOGIN:
            from django.core.exceptions import ValidationError

            raise ValidationError("Студенты входят через МЭШ", code="mesh_only")


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["mesh_enabled"] = mesh.enabled()
        ctx["password_login"] = settings.STUDENT_PASSWORD_LOGIN
        return ctx


def _redirect_uri(request):
    return request.build_absolute_uri(reverse("accounts:mesh_callback"))


def mesh_login(request):
    if not mesh.enabled():
        messages.error(request, "Вход через МЭШ ещё не подключён")
        return redirect("accounts:login")
    return redirect(mesh.authorize_url(request, _redirect_uri(request)))


def mesh_callback(request):
    if request.GET.get("error"):
        messages.error(request, "Вход через МЭШ отменён")
        return redirect("accounts:login")
    try:
        info = mesh.fetch_userinfo(request, request.GET.get("code"), request.GET.get("state"), _redirect_uri(request))
        user = mesh.match_user(info)
    except mesh.MeshError as e:
        messages.error(request, str(e))
        return redirect("accounts:login")
    if user is None:
        return render(request, "accounts/mesh_unmatched.html", status=403)
    if not user.is_active:
        messages.error(request, "Учётная запись заблокирована. Обратитесь к администратору")
        return redirect("accounts:login")
    user.must_change_password = False
    user.save(update_fields=["must_change_password"])
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect("core:home")


@login_required
def password_change(request):
    form = SetPasswordForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        user.must_change_password = False
        user.save(update_fields=["must_change_password"])
        update_session_auth_hash(request, user)
        messages.success(request, "Пароль изменён")
        return redirect("core:home")
    return render(request, "accounts/password_change.html", {"form": form})


@login_required
def profile(request):
    from achievements.models import UserAchievement

    tx = request.user.transactions.all()[:50]
    achievements = UserAchievement.objects.filter(user=request.user).select_related("achievement")
    orders = request.user.orders.select_related("variant__product").all()[:20]
    from django.db.models import Sum
    earned = request.user.transactions.filter(amount__gt=0).aggregate(total=Sum("amount"))["total"] or 0
    return render(request, "accounts/profile.html", {"transactions": tx, "achievements": achievements, "orders": orders, "earned_total": earned})


@login_required
@require_POST
def toggle_rating(request):
    request.user.hide_from_rating = not request.user.hide_from_rating
    request.user.save(update_fields=["hide_from_rating"])
    AuditLog.log(request.user, "Настройка видимости в рейтинге", request.user, hidden=request.user.hide_from_rating)
    return redirect("core:profile")
