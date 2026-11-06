from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.decorators import staff_required
from core.excel import xlsx_response

from . import services
from .models import Draw, DrawEntry


def _visible(user):
    qs = Draw.objects.all()
    if user.is_staff_role:
        return qs
    return Draw.visible_to(user, qs.exclude(status=Draw.Status.DRAFT))


@login_required
def draw_list(request):
    draws = _visible(request.user).prefetch_related("prizes")
    entered = set(DrawEntry.objects.filter(user=request.user).values_list("draw_id", flat=True))
    return render(request, "draws/list.html", {
        "active": [d for d in draws if d.status != Draw.Status.DONE],
        "done": [d for d in draws if d.status == Draw.Status.DONE][:20],
        "entered": entered,
    })


@login_required
def draw_detail(request, pk):
    draw = get_object_or_404(_visible(request.user), pk=pk)
    rows, eligible = services.eligibility(draw, request.user)
    entered = DrawEntry.objects.filter(draw=draw, user=request.user).exists()
    winners = draw.winners.select_related("user", "user__group", "prize") if draw.status == Draw.Status.DONE else []
    return render(request, "draws/detail.html", {
        "draw": draw, "rows": rows, "eligible": eligible, "entered": entered, "winners": winners,
        "entries_count": draw.entries.count(),
    })


@login_required
@require_POST
def enter(request, pk):
    draw = get_object_or_404(_visible(request.user), pk=pk)
    try:
        services.enter(draw, request.user)
        messages.success(request, "Вы участвуете в розыгрыше! Удачи 🍀")
    except services.DrawError as e:
        messages.error(request, str(e))
    return redirect("draws:detail", pk=pk)


@staff_required
def staff(request, pk):
    draw = get_object_or_404(Draw, pk=pk)
    if request.method == "POST":
        try:
            services.run(draw)
            messages.success(request, "Розыгрыш проведён")
        except services.DrawError as e:
            messages.error(request, str(e))
        return redirect("draws:staff", pk=pk)
    entries = draw.entries.select_related("user", "user__group")
    if request.GET.get("export"):
        return xlsx_response(f"draw-{pk}.xlsx", "Участники", ["ФИО", "Группа"],
                             [[e.user.full_name, e.user.group.name if e.user.group else ""] for e in entries])
    eligible_now = None
    if request.GET.get("preview"):  # подсчёт по всем студентам — по кнопке, это несколько тысяч запросов
        from accounts.models import User

        students = User.objects.filter(role=User.Role.STUDENT, expelled=False).select_related("group")
        eligible_now = sum(1 for u in students if services.eligibility(draw, u)[1])
    return render(request, "draws/staff.html", {
        "draw": draw, "entries": entries, "eligible_now": eligible_now,
        "winners": draw.winners.select_related("user", "prize", "order"),
    })
