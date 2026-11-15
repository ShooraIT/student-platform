from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import StudyGroup
from core.decorators import staff_required
from core.excel import build_workbook, workbook_response

from . import services
from .models import Answer, Completion, Question, Survey


def _visible(user):
    qs = Survey.objects.prefetch_related("tracks")
    if user.is_staff_role:
        return qs
    return Survey.visible_to(user, qs.filter(status=Survey.Status.PUBLISHED, opens_at__lte=timezone.now()))


@login_required
def survey_list(request):
    items = list(_visible(request.user))
    done = set(Completion.objects.filter(user=request.user).values_list("survey_id", flat=True))
    active = [s for s in items if not s.is_closed]
    closed = [s for s in items if s.is_closed][:20]
    return render(request, "surveys/list.html", {"active": active, "closed": closed, "done": done})


@login_required
def survey_detail(request, pk):
    survey = get_object_or_404(_visible(request.user), pk=pk)
    voted = Completion.objects.filter(survey=survey, user=request.user).exists()
    ctx = {"survey": survey, "voted": voted}
    if survey.kind == Survey.Kind.VOTE:
        ctx["options"] = survey.vote_options.all()
        if survey.results_visible_to(request.user, voted):
            ctx["results"], ctx["total"] = services.vote_results(survey)
    else:
        ctx["questions"] = survey.questions.all()
    return render(request, "surveys/detail.html", ctx)


@login_required
@require_POST
def submit(request, pk):
    survey = get_object_or_404(_visible(request.user), pk=pk)
    try:
        if survey.kind == Survey.Kind.VOTE:
            services.submit_vote(survey, request.user, request.POST.getlist("option"))
            messages.success(request, "Ваш голос учтён")
        else:
            services.submit_survey(survey, request.user, request.POST)
            messages.success(request, "Спасибо за ответы!")
    except services.SurveyError as e:
        messages.error(request, str(e))
    return redirect("surveys:detail", pk=pk)


@staff_required
def results(request, pk):
    survey = get_object_or_404(Survey, pk=pk)
    completions = survey.completions.select_related("user", "user__group")
    group_id = request.GET.get("group")
    course = request.GET.get("course")
    if group_id:
        completions = completions.filter(user__group_id=group_id)
    if course:
        completions = completions.filter(user__group__course=course)

    if request.GET.get("export"):
        return _export(survey, completions)

    ctx = {"survey": survey, "groups": StudyGroup.objects.all(), "group_id": group_id, "course": course}
    if survey.kind == Survey.Kind.VOTE:
        ctx["results"], ctx["total"] = services.vote_results(survey)
    else:
        ctx["summary"], ctx["total"] = services.survey_summary(survey, completions)
    aud = services.audience_size(survey)
    ctx["audience"] = aud
    ctx["coverage"] = round(survey.completions.count() * 100 / aud) if aud else 0
    ctx["by_group"] = (
        survey.completions.values("user__group__name").annotate(n=Count("id")).order_by("user__group__name")
    )
    return render(request, "surveys/results.html", ctx)


def _export(survey, completions):
    if survey.kind == Survey.Kind.VOTE:
        res, total = services.vote_results(survey)
        sheets = [("Итоги", ["Вариант", "Голосов", "%"], [[r["option"].title, r["count"], r["percent"]] for r in res])]
        if not survey.secret:
            rows = []
            for a in Answer.objects.filter(completion__in=completions).select_related("completion__user__group", "vote_option"):
                u = a.completion.user
                rows.append([u.full_name, u.group.name if u.group else "", a.vote_option.title])
            sheets.append(("Голоса", ["ФИО", "Группа", "Вариант"], rows))
        else:
            sheets.append(("Участники", ["ФИО", "Группа"], [[c.user.full_name, c.user.group.name if c.user.group else ""] for c in completions]))
    else:
        summary, total = services.survey_summary(survey, completions)
        srows = []
        for item in summary:
            if "options" in item:
                for o in item["options"]:
                    srows.append([item["q"].text, o["label"], o["count"], o["percent"]])
                if item.get("avg") is not None:
                    srows.append([item["q"].text, "Среднее", item["avg"], ""])
            else:
                srows.append([item["q"].text, "Текстовых ответов", len(item["texts"]), ""])
        questions = list(survey.questions.all())
        answers = {}
        for a in Answer.objects.filter(completion__in=completions):
            answers.setdefault((a.completion_id, a.question_id), []).append(a.value)
        rows = []
        for c in completions:
            rows.append(
                [c.user.full_name, c.user.group.name if c.user.group else "", timezone.localtime(c.created_at).strftime("%d.%m.%Y %H:%M")]
                + ["; ".join(answers.get((c.pk, q.pk), [])) for q in questions]
            )
        sheets = [
            ("Сводка", ["Вопрос", "Вариант", "Ответов", "%"], srows),
            ("Ответы", ["ФИО", "Группа", "Время"] + [q.text[:100] for q in questions], rows),
        ]
    return workbook_response(f"survey-{survey.pk}.xlsx", build_workbook(sheets))
