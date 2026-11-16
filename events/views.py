import calendar
import io
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone

import qrcode
import qrcode.image.svg
from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from assignments.models import Submission, Task
from core.decorators import staff_required
from core.excel import xlsx_response
from surveys.models import Completion, Survey

from . import services
from .models import Category, Event, Registration

User = get_user_model()
MONTHS = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]


def _visible_track_ids(user):
    """Return career tracks matching a student's imported specialty."""
    if user.is_staff_role:
        return None
    if not user.group_id or not user.group.specialty:
        return set()
    from career.models import Track

    code = user.group.specialty.strip().lower().split()[0].strip(" ,;")
    return {
        track.pk for track in Track.objects.filter(is_active=True)
        if code in {value.strip().lower() for value in track.specialties.split(",") if value.strip()}
    }


def _visible(user):
    qs = Event.objects.select_related("category").prefetch_related("tracks")
    if user.is_staff_role:
        return qs
    return Event.visible_to(user, qs.exclude(status=Event.Status.DRAFT))


@login_required
def calendar_view(request):
    today = timezone.localdate()
    try:
        year, month = int(request.GET.get("y", today.year)), int(request.GET.get("m", today.month))
        date(year, month, 1)
    except ValueError:
        year, month = today.year, today.month
    view = request.GET.get("view", "activities")
    if view == "calendar":
        view = "month"
    cat = request.GET.get("cat")
    mine = request.GET.get("mine") == "1"
    user = request.user
    visible_track_ids = _visible_track_ids(user)
    qs = _visible(user)
    if visible_track_ids is not None:
        qs = qs.filter(tracks__in=visible_track_ids).distinct() if visible_track_ids else qs.none()
    if cat:
        qs = qs.filter(category_id=cat)
    if mine:
        qs = qs.filter(registrations__user=request.user, registrations__status__in=Registration.ACTIVE)
    my_regs = dict(Registration.objects.filter(user=request.user).values_list("event_id", "status"))

    ctx = {"categories": Category.objects.all(), "cat": cat, "mine": mine, "view": view, "my_regs": my_regs}
    if view == "month":
        first = date(year, month, 1)
        last = date(year, month, calendar.monthrange(year, month)[1])
        tz = timezone.get_current_timezone()
        events = list(
            qs.filter(
                start__lt=timezone.make_aware(datetime.combine(last + timedelta(days=1), datetime.min.time()), tz),
                end__gte=timezone.make_aware(datetime.combine(first, datetime.min.time()), tz),
            ).order_by("start")
        )
        by_day = {}
        for e in events:
            d = timezone.localtime(e.start).date()
            by_day.setdefault(d, []).append(e)
        weeks = [
            [{"date": d, "in_month": d.month == month, "events": by_day.get(d, []), "today": d == today} for d in week]
            for week in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
        ]
        prev_m = first - timedelta(days=1)
        next_m = last + timedelta(days=1)
        ctx.update(weeks=weeks, title=f"{MONTHS[month]} {year}", prev=(prev_m.year, prev_m.month), next=(next_m.year, next_m.month))
    else:
        now = timezone.now()
        activities = []
        reg_status = dict(Registration.objects.filter(user=user).values_list("event_id", "status"))
        events = qs.filter(status=Event.Status.PUBLISHED, end__gte=now).order_by("start")
        if mine:
            events = events.filter(registrations__user=user, registrations__status__in=Registration.ACTIVE)
        for event in events:
            state = reg_status.get(event.pk)
            activities.append({
                "kind": "Событие", "type_key": "event", "icon": "▦", "title": event.title, "when": event.start,
                "detail": f"{timezone.localtime(event.start):%H:%M} · {event.location}",
                "href": reverse("events:detail", args=[event.pk]),
                "status": {
                    Registration.Status.REGISTERED: "Записан",
                    Registration.Status.ATTENDED: "Посещено",
                    Registration.Status.WAITLIST: "Лист ожидания",
                }.get(state, "Запись открыта" if event.registration_open else "Скоро"),
                "status_class": "ok" if state in Registration.ACTIVE else "",
                "reward": event.reward,
                "tracks": [track for track in event.tracks.all() if visible_track_ids is None or track.pk in visible_track_ids],
            })

        if user.can_access("tasks"):
            submissions = dict(Submission.objects.filter(user=user).values_list("task_id", "status"))
            tasks = Task.visible_to(user, Task.objects.filter(
                status=Task.Status.PUBLISHED, starts_at__lte=now, deadline__gte=now,
            ).prefetch_related("tracks")).order_by("deadline")
            if visible_track_ids is not None:
                tasks = tasks.filter(tracks__in=visible_track_ids).distinct() if visible_track_ids else tasks.none()
            if mine:
                tasks = tasks.filter(pk__in=submissions)
            for task in tasks:
                state = submissions.get(task.pk)
                status = {
                    Submission.Status.APPROVED: "Выполнено",
                    Submission.Status.SUBMITTED: "На проверке",
                    Submission.Status.REVISION: "Нужна доработка",
                    Submission.Status.FAILED: "Не пройдено",
                    Submission.Status.REJECTED: "Можно попробовать снова",
                }.get(state, "Доступно")
                activities.append({
                    "kind": "Задание", "type_key": "task", "icon": "✓", "title": task.title, "when": task.deadline,
                    "detail": f"До {timezone.localtime(task.deadline):%d.%m · %H:%M} · {task.get_kind_display()}",
                    "href": reverse("assignments:detail", args=[task.pk]), "status": status,
                    "status_class": "ok" if state == Submission.Status.APPROVED else "",
                    "reward": task.reward,
                    "tracks": [track for track in task.tracks.all() if visible_track_ids is None or track.pk in visible_track_ids],
                })

        if user.can_access("surveys"):
            completed = set(Completion.objects.filter(user=user).values_list("survey_id", flat=True))
            surveys = Survey.visible_to(user, Survey.objects.filter(
                status=Survey.Status.PUBLISHED, closes_at__gte=now,
            ).prefetch_related("tracks")).order_by("closes_at")
            if visible_track_ids is not None:
                surveys = surveys.filter(tracks__in=visible_track_ids).distinct() if visible_track_ids else surveys.none()
            if mine:
                surveys = surveys.filter(pk__in=completed)
            for survey in surveys:
                done = survey.pk in completed
                opens_later = survey.opens_at > now
                activities.append({
                    "kind": "Опрос" if survey.kind == Survey.Kind.SURVEY else "Голосование",
                    "type_key": "survey" if survey.kind == Survey.Kind.SURVEY else "vote",
                    "icon": "▤" if survey.kind == Survey.Kind.SURVEY else "◉",
                    "title": survey.title, "when": survey.closes_at,
                    "detail": f"До {timezone.localtime(survey.closes_at):%d.%m · %H:%M}",
                    "href": reverse("surveys:detail", args=[survey.pk]),
                    "status": "Пройдено" if done else "Скоро откроется" if opens_later else "Доступно",
                    "status_class": "ok" if done else "",
                    "reward": survey.reward,
                    "tracks": [track for track in survey.tracks.all() if visible_track_ids is None or track.pk in visible_track_ids],
                })
        activities.sort(key=lambda item: item["when"])
        ctx["activities"] = activities
    return render(request, "events/calendar.html", ctx)


@login_required
def detail(request, pk):
    event = get_object_or_404(_visible(request.user), pk=pk)
    reg = Registration.objects.filter(event=event, user=request.user).first()
    return render(request, "events/detail.html", {"event": event, "reg": reg})


@login_required
@require_POST
def register(request, pk):
    event = get_object_or_404(_visible(request.user), pk=pk)
    try:
        reg = services.register(event, request.user)
        if reg.status == Registration.Status.WAITLIST:
            messages.info(request, "Мест нет — вы в листе ожидания. Сообщим, если место освободится")
        else:
            messages.success(request, "Вы записаны")
    except services.EventError as e:
        messages.error(request, str(e))
    return redirect("events:detail", pk=pk)


@login_required
@require_POST
def cancel(request, pk):
    event = get_object_or_404(_visible(request.user), pk=pk)
    try:
        services.cancel(event, request.user)
        messages.success(request, "Запись отменена")
    except services.EventError as e:
        messages.error(request, str(e))
    return redirect("events:detail", pk=pk)


def _checkin_result(request, event, reg_created):
    reg, new = reg_created
    if new and event.reward:
        messages.success(request, f"Посещение отмечено! +{event.reward}")
    else:
        messages.success(request, "Посещение отмечено")


@login_required
@require_POST
def checkin_code(request, pk):
    event = get_object_or_404(_visible(request.user), pk=pk)
    try:
        _checkin_result(request, event, services.checkin_by_code(event, request.user, request.POST.get("code")))
    except services.EventError as e:
        messages.error(request, str(e))
    return redirect("events:detail", pk=pk)


@login_required
def checkin_qr(request, pk):
    event = get_object_or_404(_visible(request.user), pk=pk)
    try:
        _checkin_result(request, event, services.checkin_by_qr(event, request.user, request.GET.get("t")))
    except services.EventError as e:
        messages.error(request, str(e))
    return redirect("events:detail", pk=pk)


@login_required
def ics(request, pk):
    event = get_object_or_404(_visible(request.user), pk=pk)
    fmt = "%Y%m%dT%H%M%SZ"
    esc = lambda s: s.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")  # noqa: E731
    body = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Stepy//RU", "BEGIN:VEVENT",
        f"UID:event-{event.pk}@stepy", f"DTSTAMP:{timezone.now().astimezone(dt_timezone.utc):{fmt}}",
        f"DTSTART:{event.start.astimezone(dt_timezone.utc):{fmt}}", f"DTEND:{event.end.astimezone(dt_timezone.utc):{fmt}}",
        f"SUMMARY:{esc(event.title)}", f"LOCATION:{esc(event.location)}", f"DESCRIPTION:{esc(event.description[:500])}",
        "END:VEVENT", "END:VCALENDAR", "",
    ])
    resp = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="event-{event.pk}.ics"'
    return resp


# --- Экраны администратора ---

@staff_required
def staff_checkin(request, pk):
    event = get_object_or_404(Event, pk=pk)
    return render(request, "events/staff_checkin.html", {"event": event, "rotation": django_settings.QR_ROTATION_SECONDS})


@staff_required
def staff_qr(request, pk):
    """Текущий QR (SVG) и счётчик отметившихся — обновляется страницей каждые несколько секунд."""
    event = get_object_or_404(Event, pk=pk)
    url = request.build_absolute_uri(reverse("events:checkin_qr", args=[pk])) + "?t=" + services.current_qr_token(event)
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=12, border=2)
    buf = io.BytesIO()
    img.save(buf)
    attended = event.registrations.filter(status=Registration.Status.ATTENDED).count()
    return JsonResponse({"svg": buf.getvalue().decode(), "attended": attended, "open": event.checkin_open})


@staff_required
def staff_attendees(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "mark_all":
            for reg in event.registrations.filter(status=Registration.Status.REGISTERED).select_related("user"):
                services.mark_attended(event, reg.user, Registration.Method.LIST, request.user)
        elif action in ("mark", "unmark", "add"):
            user = get_object_or_404(User, pk=request.POST.get("user"))
            try:
                if action == "unmark":
                    services.unmark(event, user, request.user)
                else:
                    services.mark_attended(event, user, Registration.Method.LIST, request.user)
            except services.EventError as e:
                messages.error(request, str(e))
        return redirect("events:staff_attendees", pk=pk)

    regs = event.registrations.select_related("user", "user__group").exclude(status=Registration.Status.CANCELLED)
    q = request.GET.get("q", "").strip()
    found = []
    if q:
        found = User.objects.filter(role=User.Role.STUDENT, expelled=False).filter(
            Q(last_name__icontains=q) | Q(first_name__icontains=q)
        ).exclude(registrations__event=event, registrations__status=Registration.Status.ATTENDED)[:20]
    if request.GET.get("export"):
        rows = [[r.user.full_name, r.user.group.name if r.user.group else "", r.get_status_display(),
                 r.get_method_display() if r.method else "",
                 timezone.localtime(r.attended_at).strftime("%d.%m.%Y %H:%M") if r.attended_at else ""] for r in regs]
        return xlsx_response(f"event-{pk}.xlsx", "Участники", ["ФИО", "Группа", "Статус", "Способ отметки", "Время"], rows)
    stats = regs.aggregate(
        total=Count("id", filter=Q(status__in=[Registration.Status.REGISTERED, Registration.Status.ATTENDED])),
        attended=Count("id", filter=Q(status=Registration.Status.ATTENDED)),
        waitlist=Count("id", filter=Q(status=Registration.Status.WAITLIST)),
    )
    return render(request, "events/staff_attendees.html", {"event": event, "regs": regs, "q": q, "found": found, "stats": stats})
