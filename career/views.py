from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.decorators import staff_required
from core.excel import build_workbook, workbook_response
from assignments.models import Task
from events.models import Event
from surveys.models import Survey

from . import services as career
from .models import (
    DiagResult, DiagTest, Employer, ExternalAchievement, MentorBooking, MentorSlot, Resume, Track,
)

User = get_user_model()


def _fail(request, e):
    messages.error(request, str(e))


def _back(request):
    nxt = request.POST.get("next", "")
    return redirect(nxt) if nxt.startswith("/") and not nxt.startswith("//") else None


# ---------- «Мой путь» ----------

@login_required
def my_path(request):
    u = request.user
    route = career.route_status(u)
    tracks = career.my_tracks(u)
    last = u.diag_results.prefetch_related("recommended").first()
    mine = {t["track"].pk for t in tracks}
    suggest = [t for t in (last.recommended.all() if last else []) if t.pk not in mine]
    upcoming = MentorBooking.objects.filter(user=u, status=MentorBooking.Status.BOOKED, slot__start__gte=timezone.now()).select_related("slot__mentor", "slot__track")
    return render(request, "career/path.html", {
        "route": route, "tracks": tracks, "diag": last, "suggest": suggest, "test": DiagTest.objects.filter(is_active=True).first(),
        "meetings": upcoming,
    })


@login_required
def tracks(request):
    mine = set(request.user.track_enrollments.values_list("track_id", flat=True))
    rec = set()
    last = request.user.diag_results.first()
    if last:
        rec = set(last.recommended.values_list("pk", flat=True))
    items = Track.objects.filter(is_active=True).annotate(n=Count("enrollments", distinct=True))
    return render(request, "career/tracks.html", {"tracks": items, "mine": mine, "rec": rec})


@login_required
def track_detail(request, slug):
    t = get_object_or_404(Track, slug=slug, is_active=True)
    en = request.user.track_enrollments.filter(track=t).first()
    now = timezone.now()
    related_events = Event.visible_to(
        request.user, Event.objects.filter(tracks=t, status=Event.Status.PUBLISHED, end__gte=now)
    ).order_by("start")[:6]
    related_tasks = Task.visible_to(
        request.user, Task.objects.filter(tracks=t, status=Task.Status.PUBLISHED, starts_at__lte=now, deadline__gte=now)
    ).order_by("deadline")[:6] if request.user.can_access("tasks") else []
    related_surveys = Survey.visible_to(
        request.user, Survey.objects.filter(tracks=t, status=Survey.Status.PUBLISHED, opens_at__lte=now, closes_at__gte=now)
    ).order_by("closes_at")[:6] if request.user.can_access("surveys") else []
    return render(request, "career/track.html", {
        "t": t, "en": en, "p": career.track_progress(request.user, t),
        "related_events": related_events, "related_tasks": related_tasks, "related_surveys": related_surveys,
        "slots": t.slots.filter(start__gte=timezone.now(), is_cancelled=False).select_related("mentor")[:6],
        "employers": t.employers.filter(is_active=True),
        "mentors": t.mentors.filter(is_active=True),
    })


@login_required
@require_POST
def track_action(request, slug, action):
    t = get_object_or_404(Track, slug=slug)
    try:
        if action == "enroll":
            career.enroll(request.user, t)
            messages.success(request, f"Вы пробуете трек «{t.title}»")
        elif action == "leave":
            career.leave(request.user, t)
            messages.info(request, f"Вы вышли из трека «{t.title}»")
        elif action == "main":
            career.set_main(request.user, t)
            messages.success(request, f"«{t.title}» — ваш основной трек")
        else:
            raise Http404
    except career.CareerError as e:
        _fail(request, e)
    return _back(request) or redirect("career:track", slug=t.slug)


# ---------- профдиагностика ----------

@login_required
def diagnostic(request, pk):
    test = get_object_or_404(DiagTest, pk=pk, is_active=True)
    if request.method == "POST":
        try:
            r = career.submit_diagnostic(test, request.user, request.POST)
            return redirect("career:diag_result", pk=r.pk)
        except career.CareerError as e:
            _fail(request, e)
    return render(request, "career/diagnostic.html", {"test": test, "questions": test.questions.prefetch_related("options")})


@login_required
def diag_result(request, pk):
    r = get_object_or_404(DiagResult, pk=pk)
    if r.user_id != request.user.pk and not request.user.is_staff_role:
        raise PermissionDenied
    mine = set(request.user.track_enrollments.values_list("track_id", flat=True))
    return render(request, "career/diag_result.html", {"r": r, "scales": r.test.scales.all(), "mine": mine})


# ---------- встречи с наставниками ----------

@login_required
def meetings(request):
    u = request.user
    my_tracks = list(u.track_enrollments.values_list("track_id", flat=True))
    only = request.GET.get("all") != "1" and my_tracks
    slots = MentorSlot.objects.filter(start__gte=timezone.now(), is_cancelled=False).select_related("mentor", "track")
    if only:
        slots = slots.filter(track_id__in=my_tracks)
    booked = dict(MentorBooking.objects.filter(user=u).exclude(status=MentorBooking.Status.CANCELLED).values_list("slot_id", "status"))
    return render(request, "career/meetings.html", {"slots": slots[:60], "booked": booked, "only": bool(only)})


@login_required
@require_POST
def meeting_action(request, pk, action):
    slot = get_object_or_404(MentorSlot, pk=pk)
    try:
        if action == "book":
            career.book(slot, request.user)
            messages.success(request, f"Вы записаны на встречу «{slot.topic}»")
        elif action == "cancel":
            career.cancel_booking(slot, request.user)
            messages.info(request, "Запись отменена")
        else:
            raise Http404
    except career.CareerError as e:
        _fail(request, e)
    return _back(request) or redirect("career:meetings")


# ---------- кабинет наставника ----------

class SlotForm(forms.ModelForm):
    start = forms.DateTimeField(label="Начало", widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"))

    class Meta:
        model = MentorSlot
        fields = ["track", "topic", "start", "duration", "place", "capacity"]

    def __init__(self, *args, mentor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["track"].queryset = mentor.mentor_tracks.filter(is_active=True) if mentor else Track.objects.none()


@login_required
def mentor_home(request):
    u = request.user
    form = SlotForm(request.POST or None, mentor=u)
    if request.method == "POST" and form.is_valid():
        slot = form.save(commit=False)
        slot.mentor = u
        slot.save()
        messages.success(request, "Встреча опубликована — первокурсники трека увидят её в расписании")
        return redirect("career:mentor")
    slots = u.mentor_slots.select_related("track").prefetch_related("bookings__user").order_by("-start")[:30]
    return render(request, "career/mentor.html", {"form": form, "slots": slots, "stats": career.mentor_stats(u)})


@login_required
@require_POST
def mentor_close(request, pk):
    slot = get_object_or_404(MentorSlot, pk=pk)
    try:
        n = career.close_meeting(slot, request.user, request.POST.getlist("attended"))
        messages.success(request, f"Отмечено пришедших: {n}")
    except career.CareerError as e:
        _fail(request, e)
    return redirect("career:mentor")


@login_required
@require_POST
def mentor_cancel(request, pk):
    slot = get_object_or_404(MentorSlot, pk=pk, mentor=request.user)
    if not slot.held:
        slot.is_cancelled = True
        slot.save(update_fields=["is_cancelled"])
        from notifications.services import notify_many

        users = [b.user for b in slot.bookings.filter(status=MentorBooking.Status.BOOKED).select_related("user")]
        notify_many(users, f"Встреча «{slot.topic}» отменена наставником", "/career/meetings/", "event")
        messages.info(request, "Встреча отменена, записавшиеся получили уведомление")
    return redirect("career:mentor")


# ---------- работодатели ----------

@login_required
def employers(request):
    from events.models import Registration

    seen = set(Registration.objects.filter(user=request.user, status=Registration.Status.ATTENDED, event__employer__isnull=False)
               .values_list("event__employer_id", flat=True))
    track = request.GET.get("track")
    qs = Employer.objects.filter(is_active=True).prefetch_related("tracks")
    if track:
        qs = qs.filter(tracks__slug=track)
    return render(request, "career/employers.html", {"employers": qs, "seen": seen, "tracks": Track.objects.filter(is_active=True), "track": track})


@login_required
def employer_detail(request, pk):
    from events.models import Event

    e = get_object_or_404(Employer, pk=pk, is_active=True)
    now = timezone.now()
    evs = Event.visible_to(request.user, e.events.filter(status=Event.Status.PUBLISHED))
    return render(request, "career/employer.html", {"e": e, "upcoming": evs.filter(end__gte=now).order_by("start"), "past": evs.filter(end__lt=now).order_by("-start")[:10]})


# ---------- портфолио и резюме ----------

class ExternalForm(forms.ModelForm):
    date = forms.DateField(label="Дата", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    class Meta:
        model = ExternalAchievement
        fields = ["title", "issuer", "date", "file", "url"]

    def clean(self):
        d = super().clean()
        if not d.get("file") and not d.get("url"):
            raise forms.ValidationError("Приложите файл или ссылку — без подтверждения куратор не сможет проверить достижение")
        f = d.get("file")
        if f and f.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Файл больше 10 МБ")
        return d


class ResumeForm(forms.ModelForm):
    class Meta:
        model = Resume
        fields = ["headline", "about", "skills", "contacts", "show_diagnostic", "public"]
        widgets = {"about": forms.Textarea(attrs={"rows": 5})}


def _portfolio_ctx(user):
    resume = career.get_resume(user)
    return {
        "owner": user, "resume": resume, "items": career.portfolio_items(user),
        "tracks": career.my_tracks(user) if user.is_first_year else [],
        "diag": user.diag_results.first() if resume.show_diagnostic else None,
        "mentor": career.mentor_stats(user) if user.is_mentor else None,
    }


@login_required
def portfolio(request):
    ctx = _portfolio_ctx(request.user)
    ctx["external"] = request.user.external_achievements.exclude(status=ExternalAchievement.Status.APPROVED)
    ctx["public_url"] = request.build_absolute_uri(f"/p/{ctx['resume'].token}/")
    return render(request, "career/portfolio.html", ctx)


@login_required
def portfolio_add(request):
    form = ExternalForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        ea = form.save(commit=False)
        ea.user = request.user
        ea.save()
        messages.success(request, "Отправлено на проверку куратору. После подтверждения достижение появится в портфолио")
        return redirect("portfolio:index")
    return render(request, "career/portfolio_add.html", {"form": form})


@login_required
def external_file(request, pk):
    achievement = get_object_or_404(ExternalAchievement, pk=pk)
    if achievement.user_id != request.user.pk and not request.user.is_staff_role:
        raise PermissionDenied
    if not achievement.file:
        raise Http404
    return FileResponse(achievement.file.open("rb"), as_attachment=True, filename=achievement.file.name.rsplit("/", 1)[-1])


@login_required
def resume_edit(request):
    resume = career.get_resume(request.user)
    form = ResumeForm(request.POST or None, instance=resume)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Резюме сохранено")
        return redirect("portfolio:index")
    return render(request, "career/resume_edit.html", {"form": form})


@login_required
def resume_print(request):
    return render(request, "career/resume_print.html", _portfolio_ctx(request.user))


@login_required
@require_POST
def resume_token(request):
    career.regenerate_token(career.get_resume(request.user))
    messages.info(request, "Создана новая ссылка — старая больше не работает")
    return redirect("portfolio:index")


def public_portfolio(request, token):
    resume = get_object_or_404(Resume, token=token, public=True, user__is_active=True)
    ctx = _portfolio_ctx(resume.user)
    ctx["public"] = True
    return render(request, "career/resume_print.html", ctx)


# ---------- для сотрудников ----------

@staff_required
def staff_external(request):
    if request.method == "POST":
        ea = get_object_or_404(ExternalAchievement, pk=request.POST.get("id"))
        career.review_external(ea, request.user, request.POST.get("decision") == "approve", request.POST.get("comment", ""))
        messages.success(request, "Решение сохранено")
        return redirect("career:staff_external")
    pending = ExternalAchievement.objects.filter(status=ExternalAchievement.Status.PENDING).select_related("user__group")
    done = ExternalAchievement.objects.exclude(status=ExternalAchievement.Status.PENDING).select_related("user", "reviewed_by")[:30]
    return render(request, "career/staff_external.html", {"pending": pending, "done": done})


@staff_required
def staff_route(request):
    from accounts.models import StudyGroup

    group_id = request.GET.get("group") or ""
    students = User.objects.filter(role=User.Role.STUDENT, expelled=False).filter(Q(group__course=1) | Q(group__isnull=True)).select_related("group")
    if group_id:
        students = students.filter(group_id=group_id)
    rows = []
    for s in students:
        st = career.route_status(s)
        main = s.track_enrollments.filter(is_main=True).select_related("track").first()
        cur = st["current"]
        rows.append({
            "s": s, "passed": st["passed"], "total": st["total"], "percent": st["percent"],
            "current": cur["stage"].title if cur else "Маршрут пройден",
            "overdue": bool(cur and cur["overdue"]),
            "tracks": ", ".join(e.track.title for e in s.track_enrollments.select_related("track")),
            "main": main.track.title if main else "",
        })
    rows.sort(key=lambda r: (not r["overdue"], r["percent"], r["s"].last_name))
    if request.GET.get("export"):
        header = ["Группа", "Студент", "Пройдено этапов", "Текущий этап", "Просрочен", "Треки", "Основной трек"]
        data = [[str(r["s"].group or ""), r["s"].full_name, f'{r["passed"]}/{r["total"]}', r["current"], "да" if r["overdue"] else "", r["tracks"], r["main"]] for r in rows]
        return workbook_response("route-1-course.xlsx", build_workbook([("Маршрут 1 курса", header, data)]))
    return render(request, "career/staff_route.html", {
        "rows": rows, "groups": StudyGroup.objects.filter(course=1), "group_id": group_id,
        "overdue": sum(r["overdue"] for r in rows),
    })
