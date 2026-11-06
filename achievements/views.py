from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from accounts.models import StudyGroup
from wallet.models import Transaction

from . import services

User = get_user_model()


def period_start(period):
    today = timezone.localdate()
    if period == "month":
        return date(today.year, today.month, 1)
    if period == "semester":
        return date(today.year, 9, 1) if today.month >= 9 else date(today.year, 2, 1) if today.month >= 2 else date(today.year - 1, 9, 1)
    if period == "year":
        return date(today.year if today.month >= 9 else today.year - 1, 9, 1)
    return None


PERIODS = [("month", "Месяц"), ("semester", "Семестр"), ("year", "Учебный год"), ("all", "Всё время")]


def earned_filter(period):
    q = Q(transactions__kind__in=Transaction.EARNING_KINDS)
    start = period_start(period)
    if start:
        q &= Q(transactions__created_at__date__gte=start)
    return q


@login_required
def rating(request):
    period = request.GET.get("period", "month")
    scope = request.GET.get("scope", "all")
    students = User.objects.filter(role=User.Role.STUDENT, expelled=False)
    me = request.user
    if scope == "course" and me.group_id:
        students = students.filter(group__course=me.group.course)
    elif scope == "group" and me.group_id:
        students = students.filter(group=me.group)
    ranked = list(
        students.annotate(earned=Sum("transactions__amount", filter=earned_filter(period)))
        .filter(earned__gt=0)
        .select_related("group")
        .order_by("-earned", "last_name")
        .values("id", "first_name", "last_name", "group__name", "earned", "hide_from_rating")
    )
    my_place = next((i + 1 for i, r in enumerate(ranked) if r["id"] == me.pk), None)
    top = [dict(r, place=i + 1) for i, r in enumerate(ranked[:50])]
    return render(request, "achievements/rating.html", {
        "top": top, "my_place": my_place, "period": period, "scope": scope, "periods": PERIODS, "total": len(ranked),
    })


@login_required
def group_rating(request):
    period = request.GET.get("period", "month")
    start = period_start(period)
    tx = Transaction.objects.filter(kind__in=Transaction.EARNING_KINDS, user__expelled=False)
    if start:
        tx = tx.filter(created_at__date__gte=start)
    sums = dict(tx.values_list("user__group").annotate(s=Sum("amount")).values_list("user__group", "s"))
    active = dict(tx.values_list("user__group").annotate(n=Count("user", distinct=True)).values_list("user__group", "n"))
    rows = []
    for g in StudyGroup.objects.annotate(n=Count("students", filter=Q(students__expelled=False))):
        if not g.n:
            continue
        total = sums.get(g.pk, 0) or 0
        rows.append({"group": g, "avg": round(total / g.n, 1), "total": total, "active_pct": round(active.get(g.pk, 0) * 100 / g.n)})
    rows.sort(key=lambda r: -r["avg"])
    return render(request, "achievements/groups.html", {"rows": rows, "period": period, "periods": PERIODS})


@login_required
def achievements(request):
    return render(request, "achievements/list.html", {"items": services.progress_list(request.user)})
