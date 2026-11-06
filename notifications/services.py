"""Уведомления: на сайте (всегда) и Web Push (если студент подписан и включил категорию).

Пуши ставятся в очередь (Notification.push = pending) и отправляются командой `send_pushes`,
чтобы массовые рассылки не тормозили ответ сайта.
"""
import json
import logging

from django.conf import settings

from .models import CATEGORIES, Notification, PushPrefs, PushSubscription

log = logging.getLogger(__name__)

KIND_ALIASES = {"info": "announcement", "stock": "stock"}


def category(kind):
    kind = KIND_ALIASES.get(kind, kind)
    return kind if kind in CATEGORIES else "announcement"


def push_configured():
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def _wants_push(user_ids, kind):
    """Множество id пользователей, которым нужен пуш этой категории."""
    if not push_configured():
        return set()
    with_subs = set(PushSubscription.objects.filter(user_id__in=user_ids).values_list("user_id", flat=True))
    if not with_subs:
        return set()
    prefs = {p.user_id: p for p in PushPrefs.objects.filter(user_id__in=with_subs)}
    cat = category(kind)
    default = CATEGORIES[cat][1]
    return {uid for uid in with_subs if (prefs[uid].enabled(cat) if uid in prefs else default)}


def notify(user, text, url="", kind="info"):
    push = Notification.Push.PENDING if user.pk in _wants_push([user.pk], kind) else Notification.Push.NONE
    n = Notification.objects.create(user=user, text=text[:500], url=url, kind=kind, push=push)
    if push == Notification.Push.PENDING and settings.PUSH_SEND_INLINE:
        send_pending(ids=[n.pk])
    return n


def notify_many(users, text, url="", kind="info"):
    users = list(users)
    wants = _wants_push([u.pk for u in users], kind)
    objs = [
        Notification(user=u, text=text[:500], url=url, kind=kind,
                     push=Notification.Push.PENDING if u.pk in wants else Notification.Push.NONE)
        for u in users
    ]
    Notification.objects.bulk_create(objs, batch_size=500)
    return len(objs)


def _send_one(sub, payload):
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info=sub.as_info(),
            data=payload,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_SUBJECT},
            ttl=12 * 3600,
            timeout=10,
        )
        return True
    except WebPushException as e:
        status = getattr(e.response, "status_code", None)
        if status in (404, 410):  # подписка больше не действует (удалили сайт, сменили браузер)
            sub.delete()
        else:
            log.warning("Push failed %s: %s", status, e)
        return False
    except Exception as e:  # noqa: BLE001 — сеть, таймаут
        log.warning("Push failed: %s", e)
        return False


def send_pending(limit=500, ids=None):
    """Отправляет пуши из очереди. Возвращает число отправленных уведомлений."""
    qs = Notification.objects.filter(push=Notification.Push.PENDING).select_related("user").order_by("id")
    if ids is not None:
        qs = qs.filter(pk__in=ids)
    sent = 0
    for n in qs[:limit]:
        payload = json.dumps({"title": settings.PUSH_TITLE, "body": n.text, "url": n.url or "/notifications/", "tag": f"n{n.pk}"})
        ok = False
        for sub in PushSubscription.objects.filter(user=n.user):
            ok = _send_one(sub, payload) or ok
        n.push = Notification.Push.SENT if ok else Notification.Push.FAILED
        n.save(update_fields=["push"])
        sent += ok
    return sent
