from django.db import IntegrityError, transaction
from django.db.models import Sum

from notifications.services import notify

from .models import Achievement, UserAchievement


def _progress(ach, user):
    from assignments.models import Submission
    from events.models import Registration
    from shop.models import Order
    from wallet.models import Transaction

    K = Achievement.Kind
    if ach.kind == K.EVENTS:
        qs = Registration.objects.filter(user=user, status=Registration.Status.ATTENDED)
        if ach.category_id:
            qs = qs.filter(event__category_id=ach.category_id)
        return qs.count()
    if ach.kind == K.TASKS:
        return Submission.objects.filter(user=user, status=Submission.Status.APPROVED).count()
    if ach.kind == K.SURVEYS:
        return user.survey_completions.count()
    if ach.kind == K.EARNED:
        return Transaction.objects.filter(user=user, kind__in=Transaction.EARNING_KINDS).aggregate(s=Sum("amount"))["s"] or 0
    if ach.kind == K.FIRST_PURCHASE:
        return Order.objects.filter(user=user, variant__isnull=False).exclude(status=Order.Status.CANCELLED).count()
    if ach.kind == K.EVENT:
        return Registration.objects.filter(user=user, event_id=ach.event_id, status=Registration.Status.ATTENDED).count()
    return 0


def _target(ach):
    return 1 if ach.kind in (Achievement.Kind.FIRST_PURCHASE, Achievement.Kind.EVENT) else ach.count


def grant(user, ach, by=None):
    try:
        with transaction.atomic():
            UserAchievement.objects.create(user=user, achievement=ach, granted_by=by)
    except IntegrityError:
        return False
    notify(user, f"Новое достижение: {ach.icon} {ach.title}", "/profile/", "achievement")
    if ach.reward:
        from wallet import services as wallet
        from wallet.models import Transaction

        wallet.reward(user, ach.reward, Transaction.Kind.ACHIEVEMENT, f"Достижение «{ach.title}»", ("achievement", ach.pk))
    return True


def check_achievements(user):
    if not user.is_student:
        return []
    have = set(UserAchievement.objects.filter(user=user).values_list("achievement_id", flat=True))
    got = []
    for ach in Achievement.objects.filter(is_active=True).exclude(kind=Achievement.Kind.MANUAL).exclude(pk__in=have):
        if _progress(ach, user) >= _target(ach) and grant(user, ach):
            got.append(ach)
    return got


def progress_list(user):
    have = {ua.achievement_id: ua for ua in UserAchievement.objects.filter(user=user)}
    out = []
    for ach in Achievement.objects.filter(is_active=True):
        target = _target(ach)
        cur = target if ach.pk in have else min(_progress(ach, user), target) if ach.kind != Achievement.Kind.MANUAL else 0
        out.append({"a": ach, "got": have.get(ach.pk), "cur": cur, "target": target, "percent": round(cur * 100 / target) if target else 0})
    return out
