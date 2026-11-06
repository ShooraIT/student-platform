import json
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import StudyGroup
from core.decorators import staff_required
from core.models import AuditLog

from . import services
from .models import CATEGORIES, Broadcast, Notification, PushPrefs, PushSubscription

User = get_user_model()
BROADCASTS_PER_DAY = 3


@login_required
def index(request):
    items = request.user.notifications.all()[:100]
    return render(request, "notifications/index.html", {"items": items})


@login_required
def open_item(request, pk):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    n.is_read = True
    n.save(update_fields=["is_read"])
    return redirect(n.url or "notifications:index")


@login_required
@require_POST
def read_all(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect("notifications:index")


# --- Web Push ---

@never_cache
def service_worker(request):
    """Service worker отдаётся с корня сайта, чтобы управлять всеми страницами."""
    resp = HttpResponse(render_to_string("notifications/sw.js"), content_type="application/javascript")
    resp["Service-Worker-Allowed"] = "/"
    return resp


@login_required
def settings_view(request):
    prefs = PushPrefs.for_user(request.user)
    kinds = [k for k in CATEGORIES if k != "stock" or request.user.is_staff_role]
    if request.method == "POST":
        prefs.prefs = {k: (request.POST.get(k) == "1") for k in kinds}
        prefs.save()
        messages.success(request, "Настройки уведомлений сохранены")
        return redirect("notifications:settings")
    rows = [{"key": k, "label": CATEGORIES[k][0], "on": prefs.enabled(k)} for k in kinds]
    return render(request, "notifications/settings.html", {
        "rows": rows,
        "vapid_key": settings.VAPID_PUBLIC_KEY,
        "push_configured": services.push_configured(),
        "devices": request.user.push_subscriptions.all(),
    })


@login_required
@require_POST
def subscribe(request):
    try:
        data = json.loads(request.body)
        endpoint, keys = data["endpoint"], data["keys"]
        p256dh, auth = keys["p256dh"], keys["auth"]
    except (ValueError, KeyError, TypeError):
        return HttpResponseBadRequest("bad subscription")
    if not endpoint.startswith("https://"):
        return HttpResponseBadRequest("bad endpoint")
    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={"user": request.user, "p256dh": p256dh, "auth": auth, "user_agent": request.META.get("HTTP_USER_AGENT", "")[:300]},
    )
    return JsonResponse({"ok": True})


@csrf_exempt  # service worker не имеет CSRF-токена; владение подтверждается старым endpoint
@login_required
@require_POST
def resubscribe(request):
    try:
        data = json.loads(request.body)
        old = request.user.push_subscriptions.get(endpoint=data["old_endpoint"])
        new = data["subscription"]
        endpoint, keys = new["endpoint"], new["keys"]
    except (ValueError, KeyError, TypeError, PushSubscription.DoesNotExist):
        return HttpResponseBadRequest("bad subscription")
    if not endpoint.startswith("https://"):
        return HttpResponseBadRequest("bad endpoint")
    old.endpoint, old.p256dh, old.auth = endpoint, keys["p256dh"], keys["auth"]
    old.save()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def unsubscribe(request):
    try:
        endpoint = json.loads(request.body).get("endpoint", "")
    except ValueError:
        endpoint = ""
    qs = request.user.push_subscriptions.all()
    if endpoint:
        qs = qs.filter(endpoint=endpoint)
    qs.delete()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def test_push(request):
    if not request.user.push_subscriptions.exists():
        messages.error(request, "На этом аккаунте нет подключённых устройств")
    else:
        n = Notification.objects.create(user=request.user, text="Проверка: пуш-уведомления работают 🎉", url="/notifications/",
                                        kind="announcement", push=Notification.Push.PENDING)
        sent = services.send_pending(ids=[n.pk])
        if sent:
            messages.success(request, "Тестовое уведомление отправлено")
        else:
            messages.error(request, "Не удалось доставить уведомление. Попробуйте отключить и снова включить пуш")
    return redirect("notifications:settings")


# --- Объявления администрации ---

@staff_required
def broadcast(request):
    today_count = Broadcast.objects.filter(created_at__gte=timezone.now() - timedelta(days=1)).count()
    if request.method == "POST":
        text = request.POST.get("text", "").strip()
        url = request.POST.get("url", "").strip()
        if url and not url.startswith("/"):
            url = ""  # только внутренние ссылки
        group_ids = request.POST.getlist("groups")
        courses = [c for c in request.POST.getlist("courses") if c.isdigit()]
        if not text:
            messages.error(request, "Введите текст объявления")
        elif today_count >= BROADCASTS_PER_DAY and not request.user.is_superuser:
            messages.error(request, f"Не больше {BROADCASTS_PER_DAY} объявлений в сутки — иначе студенты отключат уведомления")
        else:
            students = User.objects.filter(role=User.Role.STUDENT, expelled=False, is_active=True)
            if group_ids or courses:
                students = students.filter(Q(group_id__in=group_ids) | Q(group__course__in=courses))
                label = ", ".join([f"{c} курс" for c in courses] + list(StudyGroup.objects.filter(pk__in=group_ids).values_list("name", flat=True)))
            else:
                label = "Все студенты"
            n = services.notify_many(students, text, url, "announcement")
            Broadcast.objects.create(author=request.user, text=text, url=url, audience=label, recipients=n)
            AuditLog.log(request.user, "Объявление", label, text=text, recipients=n)
            messages.success(request, f"Объявление отправлено: {n} студентам")
            return redirect("notifications:broadcast")
    return render(request, "notifications/broadcast.html", {
        "groups": StudyGroup.objects.all(), "recent": Broadcast.objects.select_related("author")[:20],
        "left": max(BROADCASTS_PER_DAY - today_count, 0),
    })
