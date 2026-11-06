"""Розыгрыши: условия участия и проверяемый случайный выбор победителей (раздел 9 ТЗ)."""
import hashlib
import random
import secrets

from django.db import transaction
from django.utils import timezone

from events.models import Registration
from notifications.services import notify

from .models import Draw, DrawCondition, DrawEntry, DrawWinner


class DrawError(Exception):
    pass


def _events_attended(user, cond):
    qs = Registration.objects.filter(user=user, status=Registration.Status.ATTENDED)
    if cond.period_start:
        qs = qs.filter(event__start__date__gte=cond.period_start)
    if cond.period_end:
        qs = qs.filter(event__start__date__lte=cond.period_end)
    if cond.category_id:
        qs = qs.filter(event__category_id=cond.category_id)
    return qs.count()


def condition_progress(cond, user):
    """Возвращает (текущее, нужно) для отображения индикатора."""
    K = DrawCondition.Kind
    if cond.kind == K.EVENTS_COUNT:
        need = cond.count or 0
        return min(_events_attended(user, cond), need), need
    if cond.kind == K.EVENT:
        ok = Registration.objects.filter(user=user, event_id=cond.event_id, status=Registration.Status.ATTENDED).exists()
    elif cond.kind == K.TASK:
        from assignments.models import Submission

        ok = Submission.objects.filter(user=user, task_id=cond.task_id, status=Submission.Status.APPROVED).exists()
    else:
        from surveys.models import Completion

        ok = Completion.objects.filter(user=user, survey_id=cond.survey_id).exists()
    return int(ok), 1


def eligibility(draw, user):
    """[(условие, текущее, нужно, выполнено)], все ли выполнены."""
    rows = []
    for c in draw.conditions.select_related("event", "task", "survey", "category"):
        cur, need = condition_progress(c, user)
        rows.append((c, cur, need, cur >= need))
    in_audience = draw.is_visible_to(user)
    return rows, in_audience and all(r[3] for r in rows)


def enter(draw, user):
    if not draw.accepting:
        raise DrawError("Приём заявок закрыт")
    _, ok = eligibility(draw, user)
    if not ok:
        raise DrawError("Условия участия ещё не выполнены")
    DrawEntry.objects.get_or_create(draw=draw, user=user)


def run(draw):
    """Проводит розыгрыш. Повторно провести нельзя."""
    from shop.models import Order

    with transaction.atomic():
        draw = Draw.objects.select_for_update().get(pk=draw.pk)
        if draw.status == Draw.Status.DONE:
            raise DrawError("Розыгрыш уже проведён")
        entries = list(draw.entries.select_related("user"))
        eligible = sorted(
            (e.user for e in entries if e.user.is_active and eligibility(draw, e.user)[1]), key=lambda u: u.pk
        )
        ids = ",".join(str(u.pk) for u in eligible)
        draw.seed = secrets.token_hex(16)
        draw.participants_hash = hashlib.sha256(ids.encode()).hexdigest()
        draw.participants_count = len(eligible)
        rng = random.Random(draw.seed)  # результат воспроизводим по seed и списку участников
        pool = eligible[:]
        rng.shuffle(pool)
        winners = []
        for prize in draw.prizes.order_by("id"):
            for _ in range(prize.quantity):
                if not pool:
                    break
                u = pool.pop(0)
                order = Order.objects.create(user=u, prize=prize, price=0, status=Order.Status.READY)
                winners.append(DrawWinner.objects.create(draw=draw, prize=prize, user=u, order=order))
        draw.status = Draw.Status.DONE
        draw.drawn_at = timezone.now()
        draw.save()
    for w in winners:
        notify(w.user, f"Вы выиграли «{w.prize.title}» в розыгрыше «{draw.title}»! Код получения: {w.order.pickup_code}",
               f"/draws/{draw.pk}/", "draw")
    return winners


def run_due():
    done = 0
    for d in Draw.objects.filter(status=Draw.Status.PUBLISHED, draw_at__lte=timezone.now()):
        run(d)
        done += 1
    return done
