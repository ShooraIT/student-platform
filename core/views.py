from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts import importer
from accounts.models import StudyGroup
from assignments.models import Submission, Task
from events.models import Event, Registration
from shop.models import Order
from surveys.models import Completion, Survey
from wallet import services as wallet
from wallet.models import Transaction

from .decorators import staff_required
from .excel import build_workbook, workbook_response
from .models import AuditLog

User = get_user_model()


@login_required
def home(request):
    if request.user.is_staff_role:
        return staff_dashboard(request)
    u = request.user
    now = timezone.now()
    my_events = Event.objects.filter(
        registrations__user=u, registrations__status=Registration.Status.REGISTERED, end__gte=now
    ).prefetch_related("tracks").order_by("start")[:5]
    upcoming = Event.visible_to(u, Event.objects.filter(status=Event.Status.PUBLISHED, end__gte=now).prefetch_related("tracks")).order_by("start")[:5]
    event_count = Event.objects.filter(registrations__user=u, registrations__status=Registration.Status.REGISTERED, end__gte=now).count()
    tasks_count = surveys_count = 0
    if u.can_access("tasks"):
        done_tasks = set(Submission.objects.filter(user=u).exclude(status__in=[Submission.Status.IN_PROGRESS, Submission.Status.REVISION]).values_list("task_id", flat=True))
        task_qs = Task.visible_to(u, Task.objects.filter(status=Task.Status.PUBLISHED, starts_at__lte=now, deadline__gte=now).prefetch_related("tracks")).order_by("deadline")
        tasks_count = task_qs.exclude(pk__in=done_tasks).count()
        tasks = [t for t in task_qs[:30] if t.pk not in done_tasks][:4]
    else:
        tasks = []
    if u.can_access("surveys"):
        done_surveys = set(Completion.objects.filter(user=u).values_list("survey_id", flat=True))
        survey_qs = Survey.visible_to(u, Survey.objects.filter(status=Survey.Status.PUBLISHED, opens_at__lte=now, closes_at__gte=now).prefetch_related("tracks"))
        surveys_count = survey_qs.exclude(pk__in=done_surveys).count()
        surveys = [s for s in survey_qs[:30] if s.pk not in done_surveys][:3]
    else:
        surveys = []
    month_start = timezone.localdate().replace(day=1)
    earned_month = Transaction.objects.filter(user=u, kind__in=Transaction.EARNING_KINDS, created_at__date__gte=month_start).aggregate(s=Sum("amount"))["s"] or 0
    my_tracks = TrackEnrollment.objects.filter(user=u).select_related("track") if u.can_access("career") else []
    from achievements.models import UserAchievement
    badges = UserAchievement.objects.filter(user=u).select_related("achievement").order_by("-created_at")[:3]
    show_balance = u.can_access("shop")
    return render(request, "core/home.html", {
        "my_events": my_events, "upcoming": upcoming, "tasks": tasks, "surveys": surveys,
        "earned_month": earned_month, "my_tracks": my_tracks, "show_balance": show_balance,
        "event_count": event_count, "tasks_count": tasks_count, "surveys_count": surveys_count, "badges": badges,
    })


@staff_required
def staff_dashboard(request):
    now = timezone.now()
    students = User.objects.filter(role=User.Role.STUDENT, expelled=False)
    ctx = {
        "students": students.count(),
        "active7": students.filter(last_login__gte=now - timedelta(days=7)).count(),
        "active30": students.filter(last_login__gte=now - timedelta(days=30)).count(),
        "to_review": Submission.objects.filter(status=Submission.Status.SUBMITTED).count(),
        "to_issue": Order.objects.filter(status__in=[Order.Status.PLACED, Order.Status.READY]).count(),
        "upcoming": Event.objects.filter(end__gte=now).exclude(status=Event.Status.CANCELLED).order_by("start")[:8],
        "on_hands": students.aggregate(s=Sum("balance"))["s"] or 0,
    }
    q = request.GET.get("student", "").strip()
    ctx["student_query"] = q
    ctx["student_matches"] = (
        students.filter(Q(last_name__icontains=q) | Q(first_name__icontains=q) | Q(username__icontains=q))
        .select_related("group")[:20] if q else []
    )
    return render(request, "core/staff_dashboard.html", ctx)


@staff_required
def staff_student_profile(request, student_id):
    """Read-only student overview for staff; mutations live behind audited actions."""
    from achievements.models import UserAchievement
    from career import services as career_services
    from career.models import TrackEnrollment

    student = get_object_or_404(User, pk=student_id, role=User.Role.STUDENT)
    if request.method == "POST" and request.POST.get("action") == "adjust_steps":
        try:
            amount = int(request.POST.get("amount", "0"))
        except ValueError:
            amount = 0
        try:
            wallet.manual_adjust(student, amount, request.POST.get("reason", ""), request.user)
            messages.success(request, f"Баланс изменён на {amount:+d} степов")
        except wallet.WalletError as e:
            messages.error(request, str(e))
        return redirect("core:staff_student_profile", student_id=student.pk)
    earned = Transaction.objects.filter(user=student, amount__gt=0).aggregate(total=Sum("amount"))["total"] or 0
    track_rows = career_services.my_tracks(student)
    achievements = UserAchievement.objects.filter(user=student).select_related("achievement")
    registrations = Registration.objects.filter(user=student).select_related("event", "event__category").order_by("-event__start")[:12]
    orders = Order.objects.filter(user=student).select_related("variant__product").order_by("-created_at")[:12]
    transactions = Transaction.objects.filter(user=student).select_related("author")[:12]

    def place(queryset):
        scores = list(queryset.annotate(score=Sum("transactions__amount", filter=Q(transactions__kind__in=Transaction.EARNING_KINDS)))
                      .filter(score__gt=0).order_by("-score", "last_name").values_list("id", "score"))
        return next((index for index, (pk, score) in enumerate(scores, 1) if pk == student.pk), None)

    students = User.objects.filter(role=User.Role.STUDENT, expelled=False)
    overall_place = place(students)
    group_place = place(students.filter(group_id=student.group_id)) if student.group_id else None
    direction_place = place(students.filter(group__specialty=student.group.specialty)) if student.group_id and student.group.specialty else None
    track_places = []
    for row in track_rows:
        track_places.append({"track": row["track"], "place": place(students.filter(track_enrollments__track=row["track"]))})
    return render(request, "core/staff_student_profile.html", {
        "student": student, "earned": earned, "achievements": achievements,
        "achievement_count": achievements.count(), "registrations": registrations,
        "orders": orders, "transactions": transactions, "tracks": track_rows,
        "overall_place": overall_place, "group_place": group_place,
        "direction_place": direction_place, "track_places": track_places,
        "portfolio_items": career_services.portfolio_items(student),
        "resume_url": reverse("career:staff_resume", args=[student.pk]),
    })


@staff_required
def import_students(request):
    """Шаг 1 — загрузка и предпросмотр, шаг 2 — подтверждение (файл хранится в сессии между шагами)."""
    import base64
    import io

    ctx = {}
    if request.GET.get("template"):
        return workbook_response("students_template.xlsx", importer.template_workbook())
    if request.method == "POST":
        if request.FILES.get("file"):
            data = request.FILES["file"].read()
            request.session["import_file"] = base64.b64encode(data).decode()
            request.session["import_name"] = request.FILES["file"].name
        elif "import_file" in request.session:
            data = base64.b64decode(request.session["import_file"])
        else:
            messages.error(request, "Выберите файл")
            return redirect("core:import_students")
        name = request.session.get("import_name", "")
        try:
            plan = importer.parse(io.BytesIO(data))
        except Exception:  # noqa: BLE001 — повреждённый или не xlsx файл
            messages.error(request, "Не удалось прочитать файл. Нужен .xlsx по шаблону")
            return redirect("core:import_students")
        if request.POST.get("apply") and not plan.errors:
            creds, expelled = importer.apply(plan, mark_missing_expelled=bool(request.POST.get("expel")))
            request.session.pop("import_file", None)
            AuditLog.log(request.user, "Импорт студентов", name, created=len(creds), updated=len(plan.to_update), expelled=expelled)
            if creds:
                return workbook_response("dostupy.xlsx", importer.credentials_workbook(creds))
            messages.success(request, f"Обновлено: {len(plan.to_update)}, выбыло: {expelled}. Новых студентов нет")
            return redirect("core:import_students")
        ctx["plan"] = plan
        ctx["filename"] = name
    return render(request, "core/import.html", ctx)


@staff_required
def manual_credit(request):
    groups = StudyGroup.objects.all()
    q = request.GET.get("q", "").strip()
    found = User.objects.filter(role=User.Role.STUDENT, expelled=False).filter(Q(last_name__icontains=q) | Q(first_name__icontains=q)).select_related("group")[:30] if q else []
    if request.method == "POST":
        ids = request.POST.getlist("users")
        group_id = request.POST.get("group")
        targets = list(User.objects.filter(pk__in=ids)) if ids else list(User.objects.filter(group_id=group_id, expelled=False)) if group_id else []
        try:
            amount = int(request.POST.get("amount", 0))
        except ValueError:
            amount = 0
        reason = request.POST.get("reason", "")
        ok = 0
        for u in targets:
            try:
                wallet.manual_credit(u, amount, reason, request.user)
                ok += 1
            except wallet.WalletError as e:
                messages.error(request, f"{u}: {e}")
                break
        if ok:
            messages.success(request, f"Начислено {amount} × {ok} студентам")
        elif not targets:
            messages.error(request, "Выберите студентов или группу")
        return redirect("core:manual_credit")
    recent = Transaction.objects.filter(kind=Transaction.Kind.MANUAL).select_related("user", "author")[:20]
    return render(request, "core/manual_credit.html", {"groups": groups, "found": found, "q": q, "recent": recent})


# --- Отчёты (раздел 12 ТЗ) ---

def _period(request):
    today = timezone.localdate()
    try:
        start = timezone.datetime.strptime(request.GET.get("from", ""), "%Y-%m-%d").date()
    except ValueError:
        start = today.replace(day=1)
    try:
        end = timezone.datetime.strptime(request.GET.get("to", ""), "%Y-%m-%d").date()
    except ValueError:
        end = today
    return start, end


REPORTS = {
    "attendance": "Посещаемость мероприятий",
    "students": "Активность студентов",
    "currency": "Оборот степов",
    "manual": "Ручные начисления",
    "shop": "Магазин",
}


@staff_required
def reports(request):
    kind = request.GET.get("kind", "attendance")
    start, end = _period(request)
    group_id = request.GET.get("group") or None
    course = request.GET.get("course") or None
    header, rows = _report(kind, start, end, group_id, course)
    if request.GET.get("export"):
        wb = build_workbook([(REPORTS.get(kind, "Отчёт"), header, rows)])
        return workbook_response(f"report-{kind}-{start}-{end}.xlsx", wb)
    return render(request, "core/reports.html", {
        "reports": REPORTS, "kind": kind, "start": start, "end": end, "header": header, "rows": rows[:300],
        "total_rows": len(rows), "groups": StudyGroup.objects.all(), "group_id": group_id, "course": course,
    })


def _students(group_id, course):
    qs = User.objects.filter(role=User.Role.STUDENT, expelled=False).select_related("group")
    if group_id:
        qs = qs.filter(group_id=group_id)
    if course:
        qs = qs.filter(group__course=course)
    return qs


def _report(kind, start, end, group_id, course):
    in_period = dict(created_at__date__gte=start, created_at__date__lte=end)
    if kind == "attendance":
        events = Event.objects.filter(start__date__gte=start, start__date__lte=end).exclude(status=Event.Status.DRAFT).select_related("category")
        rows = []
        for e in events:
            regs = e.registrations.all()
            if group_id:
                regs = regs.filter(user__group_id=group_id)
            if course:
                regs = regs.filter(user__group__course=course)
            agg = regs.aggregate(
                reg=Count("id", filter=Q(status__in=Registration.ACTIVE)),
                att=Count("id", filter=Q(status=Registration.Status.ATTENDED)),
                qr=Count("id", filter=Q(method="qr")), code=Count("id", filter=Q(method="code")), lst=Count("id", filter=Q(method="list")),
            )
            pct = round(agg["att"] * 100 / agg["reg"]) if agg["reg"] else ""
            rows.append([timezone.localtime(e.start).strftime("%d.%m.%Y %H:%M"), e.title, e.category.name, e.get_status_display(),
                         agg["reg"], agg["att"], pct, agg["qr"], agg["code"], agg["lst"]])
        return ["Дата", "Мероприятие", "Категория", "Статус", "Записались", "Пришли", "Явка, %", "QR", "Код", "Список"], rows
    if kind == "students":
        qs = _students(group_id, course).annotate(
            events=Count("registrations", filter=Q(registrations__status=Registration.Status.ATTENDED, registrations__event__start__date__gte=start, registrations__event__start__date__lte=end), distinct=True),
            tasks=Count("submissions", filter=Q(submissions__status=Submission.Status.APPROVED, submissions__submitted_at__date__gte=start, submissions__submitted_at__date__lte=end), distinct=True),
            surveys=Count("survey_completions", filter=Q(survey_completions__created_at__date__gte=start, survey_completions__created_at__date__lte=end), distinct=True),
        )
        earned = dict(Transaction.objects.filter(kind__in=Transaction.EARNING_KINDS, **in_period).values_list("user").annotate(s=Sum("amount")).values_list("user", "s"))
        rows = [[u.full_name, u.group.name if u.group else "", u.events, u.tasks, u.surveys, earned.get(u.pk, 0), u.balance,
                 timezone.localtime(u.last_login).strftime("%d.%m.%Y") if u.last_login else "не входил"] for u in qs]
        return ["ФИО", "Группа", "Мероприятий", "Заданий", "Опросов", "Заработано", "Баланс", "Последний вход"], rows
    if kind == "currency":
        tx = Transaction.objects.filter(**in_period)
        if group_id:
            tx = tx.filter(user__group_id=group_id)
        if course:
            tx = tx.filter(user__group__course=course)
        labels = dict(Transaction.Kind.choices)
        rows = [[labels.get(r["kind"], r["kind"]), r["n"], r["s"]] for r in tx.values("kind").annotate(n=Count("id"), s=Sum("amount")).order_by("kind")]
        rows.append(["Итого на балансах студентов сейчас", "", _students(group_id, course).aggregate(s=Sum("balance"))["s"] or 0])
        return ["Тип операции", "Операций", "Сумма"], rows
    if kind == "manual":
        tx = Transaction.objects.filter(kind__in=[Transaction.Kind.MANUAL, Transaction.Kind.REVERSAL], **in_period).select_related("user__group", "author")
        rows = [[timezone.localtime(t.created_at).strftime("%d.%m.%Y %H:%M"), str(t.author or ""), t.user.full_name,
                 t.user.group.name if t.user.group else "", t.amount, t.reason] for t in tx]
        return ["Когда", "Кто начислил", "Студент", "Группа", "Сумма", "Причина"], rows
    if kind == "shop":
        orders = Order.objects.filter(**in_period, variant__isnull=False)
        rows = []
        for r in orders.values("variant__product__title", "variant__name").annotate(
            n=Count("id", filter=~Q(status=Order.Status.CANCELLED)), issued=Count("id", filter=Q(status=Order.Status.ISSUED)),
            cancelled=Count("id", filter=Q(status=Order.Status.CANCELLED)), spent=Sum("price", filter=~Q(status=Order.Status.CANCELLED)),
        ):
            from shop.models import ProductVariant
            v = ProductVariant.objects.filter(product__title=r["variant__product__title"], name=r["variant__name"]).first()
            rows.append([r["variant__product__title"], r["variant__name"], r["n"], r["issued"], r["n"] - r["issued"], r["cancelled"], r["spent"] or 0, v.stock if v else ""])
        return ["Товар", "Вариант", "Продано", "Выдано", "Ожидают выдачи", "Отменено", "Потрачено степов", "Остаток"], rows
    return [], []


def healthz(request):
    return HttpResponse("ok")
