"""Автотесты критической логики (п. 16.2 ТЗ): начисления, покупки, чек-ин, видимость, опросы, розыгрыши, импорт."""
import io
import json
import time
from datetime import timedelta
from unittest import mock

from django.http import QueryDict
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts import importer
from accounts.models import StudyGroup, User
from assignments import services as task_services
from assignments.models import Submission, Task, TaskQuestion
from draws import services as draw_services
from draws.models import Draw, DrawCondition, DrawEntry, DrawPrize
from events import services as ev
from events.models import Category, Event, Registration
from shop import services as shop
from shop.models import Order, Product, ProductVariant
from surveys import services as surveys
from surveys.models import Answer, Question, Survey, VoteOption
from wallet import services as wallet
from wallet.models import Transaction


class Base(TestCase):
    def setUp(self):
        self.g1 = StudyGroup.objects.create(name="СИП-11", course=1)
        self.g2 = StudyGroup.objects.create(name="СЭС-31", course=3)
        self.admin = User.objects.create_user("adm", password="x", role=User.Role.ADMIN)
        self.st = User.objects.create_user("st", password="x", first_name="Анна", last_name="Иванова", group=self.g1)
        self.st2 = User.objects.create_user("st2", password="x", first_name="Иван", last_name="Петров", group=self.g2)
        self.cat = Category.objects.create(name="Спорт")
        now = timezone.now()
        self.event = Event.objects.create(
            title="Матч", description="-", category=self.cat, start=now - timedelta(minutes=10), end=now + timedelta(hours=1),
            location="Стадион", reward=20, status=Event.Status.PUBLISHED, checkin_code=True, code_word="ABC123",
        )


class WalletTests(Base):
    def test_reward_is_idempotent(self):
        wallet.reward(self.st, 10, Transaction.Kind.EVENT, "x", ("event", 1))
        wallet.reward(self.st, 10, Transaction.Kind.EVENT, "x", ("event", 1))
        self.st.refresh_from_db()
        self.assertEqual(self.st.balance, 10)
        self.assertEqual(Transaction.objects.filter(user=self.st).count(), 1)

    def test_balance_cannot_go_negative(self):
        with self.assertRaises(wallet.WalletError):
            wallet.charge(self.st, 5, "покупка", None)

    def test_manual_credit_limit(self):
        with self.assertRaises(wallet.WalletError):
            wallet.manual_credit(self.st, 10_000, "много", self.admin)
        with self.assertRaises(wallet.WalletError):
            wallet.manual_credit(self.st, 10, "  ", self.admin)
        wallet.manual_credit(self.st, 100, "Олимпиада", self.admin)
        self.st.refresh_from_db()
        self.assertEqual(self.st.balance, 100)

    def test_reversal(self):
        tx = wallet.manual_credit(self.st, 50, "ошибка", self.admin)
        wallet.reverse(tx, self.admin)
        self.st.refresh_from_db()
        self.assertEqual(self.st.balance, 0)
        with self.assertRaises(wallet.WalletError):
            wallet.reverse(tx, self.admin)


class EventTests(Base):
    def test_code_checkin_rewards_once(self):
        ev.checkin_by_code(self.event, self.st, "abc123")
        ev.checkin_by_code(self.event, self.st, "ABC123")
        self.st.refresh_from_db()
        self.assertEqual(self.st.balance, 20)
        self.assertEqual(Registration.objects.get(user=self.st).method, "code")

    def test_code_bruteforce_lock(self):
        for _ in range(5):
            with self.assertRaises(ev.EventError):
                ev.checkin_by_code(self.event, self.st, "WRONG")
        with self.assertRaisesMessage(ev.EventError, "Слишком много"):
            ev.checkin_by_code(self.event, self.st, "ABC123")

    @override_settings(QR_ROTATION_SECONDS=30)
    def test_qr_token_expires(self):
        token = ev.current_qr_token(self.event)
        self.assertTrue(ev.qr_token_valid(self.event, token))
        with mock.patch("events.services.time.time", return_value=time.time() + 65):
            self.assertFalse(ev.qr_token_valid(self.event, token))
            with self.assertRaises(ev.EventError):
                ev.checkin_by_qr(self.event, self.st, token)

    def test_registration_required(self):
        self.event.registration_required = True
        self.event.save()
        with self.assertRaises(ev.EventError):
            ev.checkin_by_code(self.event, self.st, "ABC123")
        # администратор по списку — может
        ev.mark_attended(self.event, self.st, Registration.Method.LIST, self.admin)
        self.assertEqual(Registration.objects.get(user=self.st).status, Registration.Status.ATTENDED)

    def test_waitlist_promotion(self):
        e = self.event
        e.start = timezone.now() + timedelta(days=1)
        e.end = e.start + timedelta(hours=1)
        e.capacity = 1
        e.save()
        ev.register(e, self.st)
        r2 = ev.register(e, self.st2)
        self.assertEqual(r2.status, Registration.Status.WAITLIST)
        ev.cancel(e, self.st)
        r2.refresh_from_db()
        self.assertEqual(r2.status, Registration.Status.REGISTERED)

    def test_audience_visibility(self):
        self.event.for_all = False
        self.event.courses = "1,2"
        self.event.save()
        self.assertTrue(self.event.is_visible_to(self.st))
        self.assertFalse(self.event.is_visible_to(self.st2))
        self.event.courses = ""
        self.event.save()
        self.event.groups.add(self.g2)
        self.assertFalse(self.event.is_visible_to(self.st))
        self.assertTrue(self.event.is_visible_to(self.st2))


class ShopTests(Base):
    def setUp(self):
        super().setUp()
        self.p = Product.objects.create(title="Кружка", price=30, status=Product.Status.ON_SALE, per_user_limit=2)
        self.v = ProductVariant.objects.create(product=self.p, stock=1)
        wallet.manual_credit(self.st, 100, "старт", self.admin)
        wallet.manual_credit(self.st2, 100, "старт", self.admin)

    def test_purchase_and_cancel_refund(self):
        o = shop.purchase(self.st, self.v.pk)
        self.st.refresh_from_db()
        self.v.refresh_from_db()
        self.assertEqual((self.st.balance, self.v.stock), (70, 0))
        with self.assertRaisesMessage(shop.ShopError, "закончился"):
            shop.purchase(self.st2, self.v.pk)
        shop.cancel(o, self.st)
        self.st.refresh_from_db()
        self.v.refresh_from_db()
        self.assertEqual((self.st.balance, self.v.stock), (100, 1))
        with self.assertRaises(shop.ShopError):
            shop.cancel(o, self.st)

    def test_insufficient_balance_keeps_stock(self):
        self.p.price = 500
        self.p.save()
        with self.assertRaises(shop.ShopError):
            shop.purchase(self.st, self.v.pk)
        self.v.refresh_from_db()
        self.assertEqual(self.v.stock, 1)
        self.assertFalse(Order.objects.exists())

    def test_issue_by_code_once(self):
        o = shop.purchase(self.st, self.v.pk)
        shop.issue(o.pickup_code.lower(), self.admin)
        with self.assertRaisesMessage(shop.ShopError, "уже выдан"):
            shop.issue(o.pickup_code, self.admin)
        with self.assertRaises(shop.ShopError):
            shop.cancel(o, self.admin)


class TaskTests(Base):
    def test_quiz_passes_and_rewards_once(self):
        t = Task.objects.create(title="Q", description="-", kind=Task.Kind.AUTO, status=Task.Status.PUBLISHED,
                                deadline=timezone.now() + timedelta(days=1), reward=20, pass_percent=50)
        q1 = TaskQuestion.objects.create(task=t, kind="text", text="?", correct="Москва\nг. Москва")
        q2 = TaskQuestion.objects.create(task=t, kind="multi", text="?", options="a\nb\nc", correct="a\nb")
        sub, pct, got = task_services.submit_quiz(t, self.st, {q1.pk: " МОСКВА ", q2.pk: ["a"]})
        self.assertEqual((pct, got), (50, 20))
        with self.assertRaises(task_services.TaskError):
            task_services.submit_quiz(t, self.st, {q1.pk: "Москва", q2.pk: ["a", "b"]})

    def test_manual_review_and_reward_limit(self):
        t = Task.objects.create(title="Фото", description="-", status=Task.Status.PUBLISHED,
                                deadline=timezone.now() + timedelta(days=1), reward=30, reward_limit=1)
        s1 = task_services.submit_manual(t, self.st, "готово", "", [])
        s2 = task_services.submit_manual(t, self.st2, "готово", "", [])
        with self.assertRaises(task_services.TaskError):
            task_services.review(s1, "reject", self.admin, "")
        task_services.review(s1, "approve", self.admin)
        task_services.review(s2, "approve", self.admin)
        self.st.refresh_from_db()
        self.st2.refresh_from_db()
        self.assertEqual((self.st.balance, self.st2.balance), (30, 0))

    def test_quest_chain(self):
        t = Task.objects.create(title="К", description="-", kind=Task.Kind.QUEST, status=Task.Status.PUBLISHED,
                                deadline=timezone.now() + timedelta(days=1), reward=10)
        TaskQuestion.objects.create(task=t, order=0, kind="text", text="1", correct="старт")
        TaskQuestion.objects.create(task=t, order=1, kind="text", text="2", correct="финиш")
        self.assertFalse(task_services.quest_answer(t, self.st, "финиш")[1])
        self.assertTrue(task_services.quest_answer(t, self.st, "Старт")[1])
        _, ok, done = task_services.quest_answer(t, self.st, "финиш")
        self.assertTrue(ok and done)
        self.assertEqual(Submission.objects.get(task=t, user=self.st).status, Submission.Status.APPROVED)


class SurveyTests(Base):
    def test_survey_once_and_required(self):
        s = Survey.objects.create(title="S", status=Survey.Status.PUBLISHED, closes_at=timezone.now() + timedelta(days=1), reward=5)
        q = Question.objects.create(survey=s, kind="single", text="?", options="Да\nНет")
        with self.assertRaises(surveys.SurveyError):
            surveys.submit_survey(s, self.st, QueryDict(""))
        surveys.submit_survey(s, self.st, QueryDict(f"q{q.pk}=Да"))
        with self.assertRaises(surveys.SurveyError):
            surveys.submit_survey(s, self.st, QueryDict(f"q{q.pk}=Нет"))
        self.st.refresh_from_db()
        self.assertEqual(self.st.balance, 5)

    def test_secret_vote_has_no_link(self):
        s = Survey.objects.create(kind=Survey.Kind.VOTE, title="V", status=Survey.Status.PUBLISHED, secret=True,
                                  closes_at=timezone.now() + timedelta(days=1))
        o = VoteOption.objects.create(survey=s, title="A")
        surveys.submit_vote(s, self.st, [o.pk])
        a = Answer.objects.get(survey=s)
        self.assertIsNone(a.completion)
        res, total = surveys.vote_results(s)
        self.assertEqual((res[0]["count"], total), (1, 1))

    def test_hidden_survey_rejected(self):
        s = Survey.objects.create(title="S", status=Survey.Status.PUBLISHED, closes_at=timezone.now() + timedelta(days=1), for_all=False)
        s.groups.add(self.g2)
        with self.assertRaises(surveys.SurveyError):
            surveys.submit_survey(s, self.st, QueryDict(""))


class DrawTests(Base):
    def test_conditions_and_run(self):
        now = timezone.now()
        d = Draw.objects.create(title="D", status=Draw.Status.PUBLISHED, entries_close=now + timedelta(days=1), draw_at=now + timedelta(days=1))
        DrawPrize.objects.create(draw=d, title="Наушники", quantity=1)
        DrawCondition.objects.create(draw=d, kind=DrawCondition.Kind.EVENT, event=self.event)
        with self.assertRaises(draw_services.DrawError):
            draw_services.enter(d, self.st)
        ev.checkin_by_code(self.event, self.st, "ABC123")
        draw_services.enter(d, self.st)
        winners = draw_services.run(d)
        self.assertEqual(len(winners), 1)
        self.assertEqual(winners[0].user, self.st)
        self.assertEqual(winners[0].order.status, Order.Status.READY)
        with self.assertRaises(draw_services.DrawError):
            draw_services.run(d)
        self.assertEqual(DrawEntry.objects.count(), 1)


class ImportTests(TestCase):
    def _xlsx(self, rows):
        wb = importer.template_workbook()
        ws = wb.active
        ws.delete_rows(2)
        for r in rows:
            ws.append(r)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    def test_import_create_update_errors(self):
        plan = importer.parse(self._xlsx([
            ["Иванова", "Мария", "Сергеевна", "СИП-21", 2, "", "m@mail.ru", "12.03.2008"],
            ["", "Без фамилии", "", "СИП-21", 2],
        ]))
        self.assertEqual((len(plan.rows), len(plan.errors)), (1, 1))
        plan.errors = []
        creds, _ = importer.apply(plan)
        self.assertEqual(len(creds), 1)
        u = creds[0][0]
        self.assertTrue(u.must_change_password)
        self.assertTrue(u.check_password(creds[0][1]))
        plan2 = importer.parse(self._xlsx([["Иванова", "Мария", "Сергеевна", "СИП-31", 3, "", "m@mail.ru", ""]]))
        self.assertEqual(len(plan2.to_update), 1)
        importer.apply(plan2)
        u.refresh_from_db()
        self.assertEqual(u.group.name, "СИП-31")


@override_settings(PUSH_SEND_INLINE=False, VAPID_PUBLIC_KEY="pub", VAPID_PRIVATE_KEY="priv")
class PushTests(Base):
    SUB = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "k1", "auth": "a1"}}

    def _subscribe(self, user, sub=None):
        self.client.force_login(user)
        return self.client.post("/notifications/push/subscribe/", data=json.dumps(sub or self.SUB), content_type="application/json")

    def test_subscribe_and_queue_respects_prefs(self):
        from notifications.models import Notification, PushPrefs
        from notifications.services import notify

        self.assertEqual(self._subscribe(self.st).status_code, 200)
        self.assertEqual(self.st.push_subscriptions.count(), 1)
        n1 = notify(self.st, "Заказ готов", kind="order")       # по умолчанию пуш включён
        n2 = notify(self.st, "+10 степов", kind="credit")       # по умолчанию выключен
        self.assertEqual((n1.push, n2.push), (Notification.Push.PENDING, Notification.Push.NONE))
        PushPrefs.objects.filter(user=self.st).update(prefs={"order": False, "credit": True})
        PushPrefs.objects.get_or_create(user=self.st, defaults={"prefs": {"order": False, "credit": True}})
        self.assertEqual(notify(self.st, "x", kind="order").push, Notification.Push.NONE)
        self.assertEqual(notify(self.st, "y", kind="credit").push, Notification.Push.PENDING)
        # у студента без подписки пуш не ставится в очередь
        self.assertEqual(notify(self.st2, "z", kind="order").push, Notification.Push.NONE)

    def test_send_and_drop_expired_subscription(self):
        from notifications.models import Notification, PushSubscription
        from notifications.services import notify, send_pending
        from pywebpush import WebPushException

        self._subscribe(self.st)
        notify(self.st, "Выигрыш!", kind="draw")
        with mock.patch("pywebpush.webpush") as wp:
            self.assertEqual(send_pending(), 1)
            payload = json.loads(wp.call_args.kwargs["data"])
            self.assertEqual(payload["body"], "Выигрыш!")
        self.assertEqual(Notification.objects.get(text="Выигрыш!").push, Notification.Push.SENT)
        notify(self.st, "Второе", kind="draw")
        gone = WebPushException("gone", response=mock.Mock(status_code=410))
        with mock.patch("pywebpush.webpush", side_effect=gone):
            self.assertEqual(send_pending(), 0)
        self.assertFalse(PushSubscription.objects.exists())

    def test_subscription_requires_https_and_owner_for_resubscribe(self):
        bad = {"endpoint": "http://evil/x", "keys": {"p256dh": "k", "auth": "a"}}
        self.assertEqual(self._subscribe(self.st, bad).status_code, 400)
        self._subscribe(self.st)
        self.client.force_login(self.st2)
        r = self.client.post("/notifications/push/resubscribe/", data=json.dumps(
            {"old_endpoint": self.SUB["endpoint"], "subscription": {"endpoint": "https://push.example/new", "keys": {"p256dh": "k", "auth": "a"}}}),
            content_type="application/json")
        self.assertEqual(r.status_code, 400)  # чужая подписка

    def test_broadcast_audience_and_daily_limit(self):
        from notifications.models import Notification

        self.client.force_login(self.admin)
        r = self.client.post("/notifications/broadcast/", {"text": "Собрание", "courses": ["1"]})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(list(Notification.objects.filter(text="Собрание").values_list("user", flat=True)), [self.st.pk])
        for i in range(3):
            self.client.post("/notifications/broadcast/", {"text": f"Ещё {i}"})
        self.assertFalse(Notification.objects.filter(text="Ещё 2").exists())

    def test_announce_on_publish(self):
        from notifications.models import Notification

        su = User.objects.create_user("su", password="x", role=User.Role.SUPERADMIN)
        self.client.force_login(su)
        now = timezone.now()
        data = {
            "title": "Новое задание", "description": "-", "kind": "manual", "status": "published",
            "starts_at_0": (now - timedelta(minutes=1)).strftime("%d.%m.%Y"), "starts_at_1": (now - timedelta(minutes=1)).strftime("%H:%M:%S"),
            "deadline_0": (now + timedelta(days=3)).strftime("%d.%m.%Y"), "deadline_1": "12:00:00",
            "reward": "10", "for_all": "", "courses": "3", "allow_text": "on", "attempts": "3", "pass_percent": "80",
            "questions-TOTAL_FORMS": "0", "questions-INITIAL_FORMS": "0", "questions-MIN_NUM_FORMS": "0", "questions-MAX_NUM_FORMS": "1000",
        }
        r = self.client.post("/admin/assignments/task/add/", data)
        self.assertEqual(r.status_code, 302, r.content.decode()[:2000])
        notified = set(Notification.objects.filter(kind="new_content").values_list("user", flat=True))
        self.assertEqual(notified, {self.st2.pk})  # только 3 курс


class StudentPagesSmokeTests(Base):
    """Все страницы студента открываются без ошибок, включая заказ и переключатель рейтинга."""

    def test_pages(self):
        p = Product.objects.create(title="Кружка", price=10, status=Product.Status.ON_SALE)
        v = ProductVariant.objects.create(product=p, stock=3)
        wallet.manual_credit(self.st, 50, "старт", self.admin)
        order = shop.purchase(self.st, v.pk)
        self.client.force_login(self.st)
        urls = ["/", "/events/", "/events/?view=list", f"/events/{self.event.pk}/", "/tasks/", "/surveys/", "/shop/",
                f"/shop/{p.pk}/", f"/shop/orders/{order.pk}/", "/draws/", "/rating/", "/rating/groups/", "/rating/badges/",
                "/profile/", "/notifications/", "/notifications/settings/"]
        for u in urls:
            self.assertEqual(self.client.get(u).status_code, 200, u)
        self.assertRedirects(self.client.post("/profile/rating-visibility/"), "/profile/")
        self.assertRedirects(self.client.post(f"/shop/orders/{order.pk}/cancel/"), "/profile/")
