from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.decorators import staff_required

from . import services
from .models import Submission, Task


def _visible(user):
    qs = Task.objects.all()
    if user.is_staff_role:
        return qs
    return Task.visible_to(user, qs.filter(status=Task.Status.PUBLISHED, starts_at__lte=timezone.now()))


@login_required
def task_list(request):
    tasks = _visible(request.user).order_by("deadline")
    subs = {s.task_id: s for s in Submission.objects.filter(user=request.user)}
    active = [t for t in tasks if t.deadline >= timezone.now()]
    past = [t for t in tasks if t.deadline < timezone.now()][:20]
    return render(request, "assignments/list.html", {"active": active, "past": past, "subs": subs})


@login_required
def task_detail(request, pk):
    task = get_object_or_404(_visible(request.user), pk=pk)
    sub = Submission.objects.filter(task=task, user=request.user).first()
    questions = list(task.questions.all())
    ctx = {"task": task, "sub": sub, "questions": questions}
    if task.kind == Task.Kind.QUEST:
        step = sub.quest_step if sub else 0
        ctx["quest_q"] = questions[step] if step < len(questions) else None
        ctx["quest_step"] = step + 1
        ctx["quest_total"] = len(questions)
    finished = sub and (sub.status in (Submission.Status.APPROVED, Submission.Status.FAILED) or not task.is_open)
    ctx["reveal"] = task.show_answers and finished
    return render(request, "assignments/detail.html", ctx)


@login_required
@require_POST
def submit(request, pk):
    task = get_object_or_404(_visible(request.user), pk=pk)
    try:
        if task.kind == Task.Kind.MANUAL:
            services.submit_manual(
                task, request.user, request.POST.get("text", ""), request.POST.get("link", ""), request.FILES.getlist("files")
            )
            messages.success(request, "Ответ отправлен на проверку")
        elif task.kind == Task.Kind.AUTO:
            answers = {}
            for q in task.questions.all():
                key = f"q{q.pk}"
                answers[q.pk] = request.POST.getlist(key) if q.kind == q.Kind.MULTI else request.POST.get(key, "")
            sub, percent, got = services.submit_quiz(task, request.user, answers)
            if got or sub.status == Submission.Status.APPROVED:
                messages.success(request, f"Результат {percent}% — задание выполнено! +{got}")
            else:
                left = task.attempts - sub.attempts_used
                messages.warning(request, f"Результат {percent}%, нужно {task.pass_percent}%. Осталось попыток: {left}")
        else:
            sub, ok, done = services.quest_answer(task, request.user, request.POST.get("answer", ""))
            if done:
                messages.success(request, "Квест пройден! Награда начислена")
            elif ok:
                messages.success(request, "Верно! Следующий вопрос открыт")
            else:
                messages.error(request, "Неверно, попробуйте ещё")
    except services.TaskError as e:
        messages.error(request, str(e))
    return redirect("assignments:detail", pk=pk)


@staff_required
def review_queue(request):
    subs = Submission.objects.filter(status=Submission.Status.SUBMITTED).select_related("task", "user", "user__group")
    task_id = request.GET.get("task")
    if task_id:
        subs = subs.filter(task_id=task_id)
    if request.method == "POST":
        ids = request.POST.getlist("ids")
        sub_id = request.POST.get("sub")
        decision = request.POST.get("decision")
        targets = Submission.objects.filter(pk__in=ids) if ids else Submission.objects.filter(pk=sub_id)
        done = 0
        for s in targets.select_related("task", "user"):
            try:
                services.review(s, decision, request.user, request.POST.get("comment", ""), request.POST.get("amount") or None)
                done += 1
            except services.TaskError as e:
                messages.error(request, f"{s.user}: {e}")
        if done:
            messages.success(request, f"Проверено ответов: {done}")
        return redirect(request.get_full_path())
    tasks = Task.objects.filter(kind=Task.Kind.MANUAL, submissions__status=Submission.Status.SUBMITTED).distinct()
    return render(request, "assignments/review.html", {"subs": subs[:100], "tasks": tasks, "task_id": task_id})
