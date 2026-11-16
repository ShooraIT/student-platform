"""Логика карьерного проекта: прогресс треков, профдиагностика, маршрут, наставники, портфолио."""
from collections import OrderedDict

from django.db import IntegrityError, transaction
from django.utils import timezone

from notifications.services import notify

from .models import (
    DiagOption, DiagResult, ExternalAchievement, MentorBooking, MentorSlot, Resume, RouteStage,
    Track, TrackEnrollment, TrackItem,
)


class CareerError(Exception):
    pass


def _check_badges(user):
    from achievements.services import check_achievements

    check_achievements(user)


# ---------- треки ----------

def _done_sets(user):
    """Что студент уже сделал — одним набором запросов для расчёта всех треков."""
    from assignments.models import Submission
    from events.models import Registration

    return {
        "events": set(Registration.objects.filter(user=user, status=Registration.Status.ATTENDED).values_list("event_id", flat=True)),
        "tasks": set(Submission.objects.filter(user=user, status=Submission.Status.APPROVED).values_list("task_id", flat=True)),
        "mentor_tracks": set(MentorBooking.objects.filter(user=user, status=MentorBooking.Status.ATTENDED).values_list("slot__track_id", flat=True)),
        "diagnostic": user.diag_results.exists(),
    }


def _item_done(item, done):
    K = TrackItem.Kind
    if item.kind == K.EVENT:
        return item.event_id in done["events"]
    if item.kind == K.TASK:
        return item.task_id in done["tasks"]
    if item.kind == K.MENTOR:
        return item.track_id in done["mentor_tracks"]
    return done["diagnostic"]


def track_progress(user, track, done=None):
    done = done or _done_sets(user)
    items = [{"item": i, "done": _item_done(i, done)} for i in track.items.select_related("event", "task")]
    req = [x for x in items if x["item"].required]
    req_done = sum(x["done"] for x in req)
    return {
        "track": track,
        "items": items,
        "required": len(req),
        "required_done": req_done,
        "optional_done": sum(x["done"] for x in items if not x["item"].required),
        "any_done": any(x["done"] for x in items),
        "percent": round(req_done * 100 / len(req)) if req else 0,
    }


def my_tracks(user):
    done = _done_sets(user)
    out = []
    for en in user.track_enrollments.select_related("track"):
        if user.is_student:
            specialty = (getattr(user.group, "specialty", "") if user.group_id else "").strip().lower()
            code = specialty.split()[0].strip(" ,;") if specialty else ""
            allowed = {value.strip().lower() for value in en.track.specialties.split(",") if value.strip()}
            if not code or code not in allowed:
                continue
        p = track_progress(user, en.track, done)
        p["enrollment"] = en
        out.append(p)
    return out


def enroll(user, track):
    if not track.is_active:
        raise CareerError("Трек закрыт")
    TrackEnrollment.objects.get_or_create(user=user, track=track)


def leave(user, track):
    user.track_enrollments.filter(track=track).delete()


def set_main(user, track):
    with transaction.atomic():
        en = TrackEnrollment.objects.filter(user=user, track=track).first()
        if not en:
            raise CareerError("Сначала запишитесь на трек")
        user.track_enrollments.update(is_main=False)
        en.is_main = True
        en.save(update_fields=["is_main"])
    _check_badges(user)


# ---------- профдиагностика ----------

def submit_diagnostic(test, user, data):
    """data — QueryDict: q<id> = id варианта. Возвращает DiagResult."""
    questions = list(test.questions.prefetch_related("options__weights__scale"))
    chosen = []
    for q in questions:
        val = data.get(f"q{q.pk}")
        opt = next((o for o in q.options.all() if str(o.pk) == val), None)
        if opt is None:
            raise CareerError("Ответьте на все вопросы")
        chosen.append(opt)
    scales = list(test.scales.prefetch_related("tracks"))
    # Максимум считается отдельно по каждой шкале для перевода в проценты.
    max_pts = {s.pk: 0 for s in scales}
    for q in questions:
        best = {}
        for o in q.options.all():
            weights = list(o.weights.all())
            if weights:
                for w in weights:
                    best[w.scale_id] = max(best.get(w.scale_id, 0), w.points)
            else:  # Старые диагностики продолжают работать до заполнения весов по шкалам.
                best[o.scale_id] = max(best.get(o.scale_id, 0), o.points)
        for sid, pts in best.items():
            max_pts[sid] = max_pts.get(sid, 0) + pts
    got = {s.pk: 0 for s in scales}
    for o in chosen:
        weights = list(o.weights.all())
        if weights:
            for w in weights:
                got[w.scale_id] = got.get(w.scale_id, 0) + w.points
        else:
            got[o.scale_id] = got.get(o.scale_id, 0) + o.points
    scores = OrderedDict()
    for s in sorted(scales, key=lambda s: -got[s.pk] / (max_pts[s.pk] or 1)):
        scores[s.name] = round(got[s.pk] * 100 / max_pts[s.pk]) if max_pts[s.pk] else 0
    top = sorted(scales, key=lambda s: -got[s.pk] / (max_pts[s.pk] or 1))[:2]
    rec = []
    for s in top:
        for t in s.tracks.filter(is_active=True):
            if t not in rec:
                rec.append(t)
    result = DiagResult.objects.create(user=user, test=test, scores=scores)
    result.recommended.set(rec[:3])
    _check_badges(user)
    return result


# ---------- маршрут первокурсника ----------

def route_metrics(user):
    from events.models import Registration

    done = _done_sets(user)
    tried = sum(1 for en in user.track_enrollments.select_related("track")
                if track_progress(user, en.track, done)["any_done"])
    resume = Resume.objects.filter(user=user).first()
    return {
        RouteStage.Condition.ACTIVITIES: len(done["events"]),
        RouteStage.Condition.DIAGNOSTIC: 1 if done["diagnostic"] else 0,
        RouteStage.Condition.TRACKS: tried,
        RouteStage.Condition.MENTOR: MentorBooking.objects.filter(user=user, status=MentorBooking.Status.ATTENDED).count(),
        RouteStage.Condition.EMPLOYERS: Registration.objects.filter(
            user=user, status=Registration.Status.ATTENDED, event__employer__isnull=False
        ).values("event__employer").distinct().count(),
        RouteStage.Condition.MAIN_TRACK: user.track_enrollments.filter(is_main=True).count(),
        RouteStage.Condition.RESUME: 1 if resume and resume.is_filled else 0,
        RouteStage.Condition.PORTFOLIO: len(portfolio_items(user)),
    }


def route_status(user, metrics=None):
    """Этапы с выполнением условий. Текущий этап — первый невыполненный."""
    m = metrics or route_metrics(user)
    today = timezone.localdate()
    stages, current = [], None
    for st in RouteStage.objects.prefetch_related("conditions"):
        conds = []
        for c in st.conditions.all():
            target = 1 if c.kind in (RouteStage.Condition.DIAGNOSTIC, RouteStage.Condition.MAIN_TRACK, RouteStage.Condition.RESUME) else c.count
            cur = min(m.get(c.kind, 0), target)
            conds.append({"c": c, "cur": cur, "target": target, "done": cur >= target})
        done = all(x["done"] for x in conds)
        row = {"stage": st, "conds": conds, "done": done, "overdue": not done and st.deadline and st.deadline < today}
        if not done and current is None:
            current = row
            row["current"] = True
        stages.append(row)
    total = len(stages)
    passed = sum(1 for s in stages if s["done"])
    return {"stages": stages, "current": current, "passed": passed, "total": total,
            "percent": round(passed * 100 / total) if total else 0}


# ---------- наставники ----------

def book(slot, user):
    with transaction.atomic():
        slot = MentorSlot.objects.select_for_update().get(pk=slot.pk)
        if slot.is_cancelled or slot.is_past:
            raise CareerError("Запись на эту встречу закрыта")
        if slot.mentor_id == user.pk:
            raise CareerError("Нельзя записаться к себе")
        b = MentorBooking.objects.filter(slot=slot, user=user).first()
        if b and b.status != MentorBooking.Status.CANCELLED:
            raise CareerError("Вы уже записаны")
        if slot.free < 1:
            raise CareerError("Мест нет")
        if b:
            b.status = MentorBooking.Status.BOOKED
            b.save(update_fields=["status"])
        else:
            b = MentorBooking.objects.create(slot=slot, user=user)
    notify(slot.mentor, f"{user.short_name} записался на встречу «{slot.topic}»", "/career/mentor/", "event")
    return b


def cancel_booking(slot, user):
    n = MentorBooking.objects.filter(slot=slot, user=user, status=MentorBooking.Status.BOOKED).update(status=MentorBooking.Status.CANCELLED)
    if not n:
        raise CareerError("Записи нет")


def close_meeting(slot, mentor, attended_ids):
    """Наставник отмечает пришедших. Первокурсники получают награду, наставник — за проведённую встречу."""
    from core.models import SiteSettings
    from wallet import services as wallet
    from wallet.models import Transaction

    if slot.mentor_id != mentor.pk and not mentor.is_staff_role:
        raise CareerError("Это не ваша встреча")
    if slot.start > timezone.now():
        raise CareerError("Отметить участников можно после начала встречи")
    s = SiteSettings.get()
    attended_ids = {int(x) for x in attended_ids}
    came = []
    with transaction.atomic():
        for b in slot.bookings.exclude(status=MentorBooking.Status.CANCELLED).select_related("user"):
            new = MentorBooking.Status.ATTENDED if b.user_id in attended_ids else MentorBooking.Status.MISSED
            if b.status != new:
                b.status = new
                b.save(update_fields=["status"])
            if new == MentorBooking.Status.ATTENDED:
                came.append(b.user)
        slot.held = bool(came)
        slot.save(update_fields=["held"])
    for u in came:
        wallet.reward(u, s.mentor_meeting_reward, Transaction.Kind.MENTOR_MEETING, f"Встреча с наставником: {slot.topic}", ("mentor_slot", slot.pk))
        _check_badges(u)
    if came:
        wallet.reward(slot.mentor, s.mentoring_reward, Transaction.Kind.MENTORING, f"Проведена встреча: {slot.topic}", ("mentoring", slot.pk))
    return len(came)


def mentor_stats(user):
    held = MentorSlot.objects.filter(mentor=user, held=True)
    mentees = MentorBooking.objects.filter(slot__mentor=user, status=MentorBooking.Status.ATTENDED).values("user").distinct().count()
    return {"meetings": held.count(), "mentees": mentees}


# ---------- портфолио ----------

def portfolio_items(user, public=False):
    """Подтверждённые записи портфолио: что засчитала платформа и что подтвердил куратор."""
    from achievements.models import UserAchievement
    from assignments.models import Submission
    from events.models import Registration

    items = []
    for r in Registration.objects.filter(user=user, status=Registration.Status.ATTENDED).select_related("event__employer", "event__category"):
        e = r.event
        kind = "Работодатель" if e.employer_id else e.category.name
        items.append({"date": e.start.date(), "title": e.title, "kind": kind,
                      "detail": e.employer.name if e.employer_id else e.location, "source": "Подтверждено колледжем"})
    for sub in Submission.objects.filter(user=user, status=Submission.Status.APPROVED).select_related("task"):
        items.append({"date": (sub.reviewed_at or sub.submitted_at).date(), "title": sub.task.title, "kind": "Проект",
                      "detail": "Принят проверяющим", "source": "Подтверждено колледжем"})
    for b in MentorBooking.objects.filter(user=user, status=MentorBooking.Status.ATTENDED).select_related("slot__track"):
        items.append({"date": b.slot.start.date(), "title": f"Встреча с наставником: {b.slot.topic}", "kind": "Наставничество",
                      "detail": b.slot.track.title, "source": "Подтверждено наставником"})
    st = mentor_stats(user)
    if st["meetings"]:
        last = MentorSlot.objects.filter(mentor=user, held=True).order_by("-start").first()
        items.append({"date": last.start.date(), "title": f"Наставник первокурсников: {st['meetings']} встреч, {st['mentees']} подопечных",
                      "kind": "Наставничество", "detail": "Опыт наставника", "source": "Подтверждено колледжем"})
    for ea in ExternalAchievement.objects.filter(user=user, status=ExternalAchievement.Status.APPROVED):
        items.append({"date": ea.date or ea.created_at.date(), "title": ea.title, "kind": "Внешнее достижение",
                      "detail": ea.issuer, "source": "Подтверждено куратором", "url": ea.url})
    for ua in UserAchievement.objects.filter(user=user).select_related("achievement"):
        items.append({"date": ua.created_at.date(), "title": f"{ua.achievement.icon} {ua.achievement.title}", "kind": "Значок",
                      "detail": ua.achievement.description, "source": "Выдан платформой"})
    items.sort(key=lambda x: x["date"], reverse=True)
    return items


def review_external(ea, reviewer, approve, comment=""):
    ea.status = ExternalAchievement.Status.APPROVED if approve else ExternalAchievement.Status.REJECTED
    ea.reviewed_by = reviewer
    ea.comment = comment[:255]
    ea.save(update_fields=["status", "reviewed_by", "comment"])
    text = f"Достижение «{ea.title}» {'подтверждено и добавлено в портфолио' if approve else 'отклонено'}"
    notify(ea.user, text + (f": {comment}" if comment and not approve else ""), "/portfolio/", "task")


def get_resume(user):
    return Resume.objects.get_or_create(user=user)[0]


def regenerate_token(resume):
    from .models import gen_token

    for _ in range(5):
        resume.token = gen_token()
        try:
            with transaction.atomic():
                resume.save(update_fields=["token"])
            return
        except IntegrityError:
            continue


def issue_fund(item, user, issued_by=None, *, size="", note=""):
    """Выдать предмет фонда с уменьшением остатка; временный фонд затем можно вернуть."""
    from .models import FundIssue, FundItem

    with transaction.atomic():
        locked = FundItem.objects.select_for_update().get(pk=item.pk)
        if locked.stock < 1:
            raise CareerError("Предмета нет в наличии")
        locked.stock -= 1
        locked.save(update_fields=["stock"])
        return FundIssue.objects.create(item=locked, user=user, issued_by=issued_by, size=size, note=note)


def return_fund(issue, *, note=None):
    from .models import FundIssue

    with transaction.atomic():
        locked = FundIssue.objects.select_for_update().select_related("item").get(pk=issue.pk)
        if locked.item.kind != locked.item.Kind.LOAN:
            raise CareerError("Велком-набор не относится к возвратному фонду")
        if locked.returned_at:
            raise CareerError("Предмет уже возвращён")
        locked.returned_at = timezone.now()
        if note is not None:
            locked.note = note[:200]
        locked.save(update_fields=["returned_at", "note"])
        locked.item.stock += 1
        locked.item.save(update_fields=["stock"])
        return locked
