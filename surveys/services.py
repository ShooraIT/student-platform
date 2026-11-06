from collections import Counter

from django.db import IntegrityError, transaction

from wallet import services as wallet
from wallet.models import Transaction

from .models import Answer, Completion, Question, Survey


class SurveyError(Exception):
    pass


def _check_open(survey, user):
    if not survey.is_open:
        raise SurveyError("Приём ответов закрыт")
    if not survey.is_visible_to(user):
        raise SurveyError("Опрос недоступен для вашей группы")


def _complete(survey, user):
    try:
        with transaction.atomic():
            return Completion.objects.create(survey=survey, user=user)
    except IntegrityError:
        raise SurveyError("Вы уже ответили")


def submit_survey(survey, user, data):
    """data: QueryDict с полями q<id>."""
    _check_open(survey, user)
    rows = []
    for q in survey.questions.all():
        key = f"q{q.pk}"
        values = data.getlist(key) if q.kind == Question.Kind.MULTI else [data.get(key, "")]
        values = [v.strip() for v in values if v and v.strip()]
        if q.kind in Question.CHOICE_KINDS and any(v not in q.option_list() for v in values):
            raise SurveyError("Недопустимый вариант ответа")
        if q.kind in Question.SCALE_KINDS and values and values[0] not in [str(i) for i in q.scale_range()]:
            raise SurveyError("Недопустимое значение шкалы")
        if q.required and not values:
            raise SurveyError(f"Ответьте на вопрос: «{q.text}»")
        rows += [(q, v[:5000]) for v in values]
    with transaction.atomic():
        c = _complete(survey, user)
        Answer.objects.bulk_create([Answer(survey=survey, completion=c, question=q, value=v) for q, v in rows])
    wallet.reward(user, survey.reward, Transaction.Kind.SURVEY, f"Опрос: {survey.title}", ("survey", survey.pk))
    return c


def submit_vote(survey, user, option_ids):
    _check_open(survey, user)
    option_ids = list(dict.fromkeys(int(i) for i in option_ids if str(i).isdigit()))
    if not option_ids:
        raise SurveyError("Выберите вариант")
    if len(option_ids) > survey.max_choices:
        raise SurveyError(f"Можно выбрать не больше {survey.max_choices}")
    options = list(survey.vote_options.filter(pk__in=option_ids))
    if len(options) != len(option_ids):
        raise SurveyError("Недопустимый вариант")
    with transaction.atomic():
        c = _complete(survey, user)
        # При тайном голосовании ответ не связан с фактом участия
        Answer.objects.bulk_create(
            [Answer(survey=survey, completion=None if survey.secret else c, vote_option=o) for o in options]
        )
    wallet.reward(user, survey.reward, Transaction.Kind.VOTE, f"Голосование: {survey.title}", ("survey", survey.pk))
    return c


def vote_results(survey):
    counts = Counter(Answer.objects.filter(survey=survey, vote_option__isnull=False).values_list("vote_option_id", flat=True))
    total = survey.completions.count()
    res = [(o, counts.get(o.pk, 0)) for o in survey.vote_options.all()]
    res.sort(key=lambda x: -x[1])
    return [{"option": o, "count": n, "percent": round(n * 100 / total) if total else 0} for o, n in res], total


def survey_summary(survey, completions=None):
    completions = completions if completions is not None else survey.completions.all()
    answers = Answer.objects.filter(completion__in=completions)
    total = completions.count()
    out = []
    for q in survey.questions.all():
        vals = [a.value for a in answers if a.question_id == q.pk]
        item = {"q": q, "count": len(set(a.completion_id for a in answers if a.question_id == q.pk))}
        if q.kind in Question.CHOICE_KINDS:
            c = Counter(vals)
            item["options"] = [
                {"label": o, "count": c.get(o, 0), "percent": round(c.get(o, 0) * 100 / total) if total else 0}
                for o in q.option_list()
            ]
        elif q.kind in Question.SCALE_KINDS:
            nums = [int(v) for v in vals if v.isdigit()]
            item["avg"] = round(sum(nums) / len(nums), 2) if nums else None
            c = Counter(nums)
            item["options"] = [
                {"label": str(i), "count": c.get(i, 0), "percent": round(c.get(i, 0) * 100 / total) if total else 0}
                for i in q.scale_range()
            ]
        else:
            item["texts"] = vals
        out.append(item)
    return out, total


def audience_size(survey):
    from accounts.models import User

    students = User.objects.filter(role=User.Role.STUDENT, expelled=False)
    if survey.for_all:
        return students.count()
    groups = set(survey.groups.values_list("pk", flat=True))
    courses = {int(c) for c in survey.courses.split(",") if c.strip().isdigit()}
    from django.db.models import Q

    return students.filter(Q(group__in=groups) | Q(group__course__in=courses)).count()


