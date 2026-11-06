"""Все изменения баланса проходят только через этот модуль."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from core.models import AuditLog, SiteSettings

from .models import Transaction

User = get_user_model()


class WalletError(Exception):
    pass


def _apply(user_id, amount, kind, reason, *, source=None, author=None, reverses=None):
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user_id)
        if user.balance + amount < 0:
            raise WalletError("Недостаточно степов на балансе")
        source_type, source_id = (source[0], source[1]) if source else ("", None)
        try:
            with transaction.atomic():
                tx = Transaction.objects.create(
                    user=user,
                    amount=amount,
                    kind=kind,
                    source_type=source_type,
                    source_id=source_id,
                    reason=reason[:255],
                    author=author,
                    reverses=reverses,
                )
        except IntegrityError:
            return None  # уже начислено за этот источник
        user.balance += amount
        user.save(update_fields=["balance"])
    _after_credit(user, tx)
    return tx


def _after_credit(user, tx):
    if tx.amount > 0 and tx.kind in Transaction.EARNING_KINDS:
        from notifications.services import notify

        s = SiteSettings.get()
        notify(user, f"Начислено {tx.amount} {s.plural(tx.amount)}: {tx.reason}", url="/profile/", kind="credit")
        if tx.kind != Transaction.Kind.ACHIEVEMENT:
            from achievements.services import check_achievements

            check_achievements(user)


def reward(user, amount, kind, reason, source):
    """Автоматическое начисление за действие. source = ("event", id). Повторно не начисляется."""
    if amount <= 0:
        return None
    return _apply(user.pk, amount, kind, reason, source=source)


def manual_credit(user, amount, reason, author):
    if amount <= 0:
        raise WalletError("Сумма должна быть положительной")
    if not reason.strip():
        raise WalletError("Укажите причину начисления")
    s = SiteSettings.get()
    if not author.is_superuser:
        if amount > s.manual_credit_limit:
            raise WalletError(f"Превышен лимит одного начисления ({s.manual_credit_limit})")
        today = (
            Transaction.objects.filter(
                author=author, kind=Transaction.Kind.MANUAL, created_at__gte=timezone.now() - timedelta(days=1)
            ).aggregate(s=Sum("amount"))["s"]
            or 0
        )
        if today + amount > s.manual_daily_limit:
            raise WalletError(f"Превышен суточный лимит ручных начислений ({s.manual_daily_limit})")
    tx = _apply(user.pk, amount, Transaction.Kind.MANUAL, reason, author=author)
    AuditLog.log(author, "Ручное начисление", user, amount=amount, reason=reason)
    return tx


def reverse(tx, author, reason="Сторно"):
    if tx.amount <= 0 or hasattr(tx, "reversed_by"):
        raise WalletError("Эту операцию нельзя отменить")
    new = _apply(tx.user_id, -tx.amount, Transaction.Kind.REVERSAL, f"{reason}: {tx.reason}", author=author, reverses=tx)
    AuditLog.log(author, "Сторно", tx.user, amount=tx.amount, transaction=tx.pk)
    return new


def charge(user, amount, reason, source):
    """Списание за покупку. Вызывать внутри transaction.atomic вместе с изменением остатков."""
    return _apply(user.pk, -amount, Transaction.Kind.PURCHASE, reason, source=None) if amount > 0 else None


def refund(user, amount, reason, source):
    return _apply(user.pk, amount, Transaction.Kind.REFUND, reason, source=source) if amount > 0 else None
