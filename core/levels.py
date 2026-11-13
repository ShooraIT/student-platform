"""Уровни студента (по макету 01:17: «LEVEL 06 · 155 / 200»).

Уровень растёт от заработанных за всё время степов; покупки уровень не снижают.
"""
from django.conf import settings
from django.db.models import Sum


def level_info(user):
    from wallet.models import Transaction

    step = getattr(settings, "LEVEL_STEPS", 200)
    earned = Transaction.objects.filter(user=user, kind__in=Transaction.EARNING_KINDS).aggregate(s=Sum("amount"))["s"] or 0
    earned = max(earned, 0)
    cur = earned % step
    return {"level": earned // step + 1, "earned": earned, "current": cur, "step": step, "percent": round(cur * 100 / step)}
