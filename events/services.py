import hashlib
import hmac
import time
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from notifications.services import notify
from wallet import services as wallet
from wallet.models import Transaction

from .models import CodeAttempt, Event, Registration


class EventError(Exception):
    pass


# --- Запись ---

def register(event, user):
    if not event.registration_open:
        raise EventError("Запись закрыта")
    if not event.is_visible_to(user):
        raise EventError("Мероприятие недоступно для вашей группы")
    with transaction.atomic():
        Event.objects.select_for_update().get(pk=event.pk)
        reg = Registration.objects.filter(event=event, user=user).first()
        if reg and reg.status != Registration.Status.CANCELLED:
            return reg
        left = event.seats_left()  # считаем до создания записи
        status = Registration.Status.WAITLIST if left == 0 else Registration.Status.REGISTERED
        if reg:
            reg.status = status
            reg.save()
        else:
            reg = Registration.objects.create(event=event, user=user, status=status)
    return reg


def cancel(event, user):
    if timezone.now() >= event.start:
        raise EventError("Мероприятие уже началось")
    with transaction.atomic():
        Event.objects.select_for_update().get(pk=event.pk)
        reg = Registration.objects.filter(event=event, user=user).first()
        if not reg or reg.status == Registration.Status.ATTENDED:
            return
        was_active = reg.status == Registration.Status.REGISTERED
        reg.status = Registration.Status.CANCELLED
        reg.save()
        if was_active:
            nxt = event.registrations.filter(status=Registration.Status.WAITLIST).order_by("created_at").first()
            if nxt:
                nxt.status = Registration.Status.REGISTERED
                nxt.save()
                notify(nxt.user, f"Освободилось место: вы записаны на «{event.title}»", f"/events/{event.pk}/", "event")


# --- Чек-ин ---

def _qr_token(event_id, slot):
    msg = f"{event_id}:{slot}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:16]


def current_qr_token(event):
    return _qr_token(event.pk, int(time.time()) // settings.QR_ROTATION_SECONDS)


def qr_token_valid(event, token):
    slot = int(time.time()) // settings.QR_ROTATION_SECONDS
    return any(hmac.compare_digest(_qr_token(event.pk, s), token or "") for s in (slot, slot - 1))


def mark_attended(event, user, method, by=None):
    """Отмечает посещение и начисляет награду (один раз)."""
    if event.status != Event.Status.PUBLISHED:
        raise EventError("Мероприятие не опубликовано")
    with transaction.atomic():
        reg, created = Registration.objects.select_for_update().get_or_create(event=event, user=user)
        if reg.status == Registration.Status.ATTENDED:
            return reg, False
        if event.registration_required and method != Registration.Method.LIST and (
            created or reg.status not in (Registration.Status.REGISTERED,)
        ):
            if created:
                reg.delete()
            raise EventError("Отметиться могут только записавшиеся на мероприятие")
        reg.status = Registration.Status.ATTENDED
        reg.method = method
        reg.attended_at = timezone.now()
        reg.marked_by = by
        reg.save()
    wallet.reward(user, event.reward, Transaction.Kind.EVENT, f"Посещение: {event.title}", ("event", event.pk))
    return reg, True


def unmark(event, user, by):
    reg = Registration.objects.filter(event=event, user=user, status=Registration.Status.ATTENDED).first()
    if not reg:
        return
    reg.status = Registration.Status.REGISTERED
    reg.method, reg.attended_at = "", None
    reg.save()
    tx = Transaction.objects.filter(
        user=user, kind=Transaction.Kind.EVENT, source_type="event", source_id=event.pk
    ).first()
    if tx and not hasattr(tx, "reversed_by"):
        try:
            wallet.reverse(tx, by, "Снята отметка посещения")
        except wallet.WalletError:
            pass
        # повторное начисление при новой отметке: снимаем идемпотентность, переименовав источник
        Transaction.objects.filter(pk=tx.pk).update(source_type="event-reversed")


def checkin_by_code(event, user, code):
    window = timezone.now() - timedelta(minutes=10)
    if CodeAttempt.objects.filter(user=user, created_at__gte=window).count() >= 5:
        raise EventError("Слишком много неверных попыток. Подождите 10 минут")
    if not event.checkin_code:
        raise EventError("Для этого мероприятия отметка по кодовому слову не используется")
    if not event.checkin_open:
        raise EventError("Отметка сейчас закрыта")
    if (code or "").strip().upper() != event.code_word.upper():
        CodeAttempt.objects.create(user=user)
        raise EventError("Неверное кодовое слово")
    return mark_attended(event, user, Registration.Method.CODE)


def checkin_by_qr(event, user, token):
    if not event.checkin_qr:
        raise EventError("Для этого мероприятия отметка по QR-коду не используется")
    if not event.checkin_open:
        raise EventError("Отметка сейчас закрыта")
    if not qr_token_valid(event, token):
        raise EventError("QR-код устарел. Отсканируйте код на экране ещё раз")
    return mark_attended(event, user, Registration.Method.QR)
