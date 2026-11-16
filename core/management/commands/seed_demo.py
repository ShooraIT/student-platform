"""Демо-данные для показа и проверки. НЕ запускать на боевой базе.

Перед запуском задайте переменные DEMO_ADMIN_PASSWORD, DEMO_ORG_PASSWORD,
DEMO_STUDENT_PASSWORD. Команда не задаёт встроенные пароли.
"""
import os
import random
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from achievements.models import Achievement
from assignments.models import Task, TaskQuestion
from career.models import Employer, FundItem, MentorSlot, Track, TrackItem
from events.models import Category, Event
from events.services import mark_attended
from shop.models import Product, ProductVariant
from surveys.models import Question, Survey, VoteOption

class Command(BaseCommand):
    help = "Заполнить базу демо-данными"

    @transaction.atomic
    def handle(self, *args, **opts):
        if User.objects.filter(username="admin").exists():
            self.stdout.write("Демо-данные уже есть")
            return
        password_env = {
            "admin": "DEMO_ADMIN_PASSWORD",
            "org": "DEMO_ORG_PASSWORD",
            "students": "DEMO_STUDENT_PASSWORD",
        }
        passwords = {name: os.environ.get(env_name) for name, env_name in password_env.items()}
        missing = [env_name for name, env_name in password_env.items() if not passwords[name]]
        if missing:
            raise CommandError(
                "Перед запуском задайте переменные окружения: " + ", ".join(missing)
            )
        rnd = random.Random(1)
        now = timezone.now()
        User.objects.create_user("admin", password=passwords["admin"], first_name="Анна", last_name="Админова", role=User.Role.SUPERADMIN)
        User.objects.create_user("org", password=passwords["org"], first_name="Олег", last_name="Организаторов", role=User.Role.ADMIN)

        call_command("sync_study_groups", stdout=self.stdout)
        call_command("seed_demo_students", stdout=self.stdout)
        students = list(User.objects.filter(username__startswith="demo-").select_related("group"))

        cats = {n: Category.objects.create(name=n, color=c) for n, c in
                [("Спорт", "#2e7d4f"), ("Творчество", "#cb563d"), ("Учёба", "#f1a627"), ("Волонтёрство", "#cb563d"), ("Профориентация", "#1d1f27")]}
        all_track_slugs = list(Track.objects.filter(is_active=True).values_list("slug", flat=True))
        employers = [
            Employer.objects.get(name="ВР Концепт"),
            Employer.objects.get(name="Код безопасности"),
            Employer.objects.get(name="Stella Di Mosca"),
        ]
        today = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
        ev_specs = [
            ("Экскурсия в Stella Di Mosca: как устроена работа отеля", "Профориентация", -10, 15, "Stella Di Mosca", 10, 2, ["hospitality"]),
            ("Разговор со старшекурсниками: как выбрать профессиональный трек", "Профориентация", -5, 16, "Ауд. 204", 10, None, all_track_slugs),
            ("Профпроба: один день в дизайн-мастерской", "Профориентация", -2, 10, "Дизайн-лаборатория колледжа", 10, None, ["creative-design", "creative-animation"]),
            ("Встреча с HR компании «Код безопасности»: резюме и первое собеседование", "Профориентация", 0, timezone.localtime(now).hour, "Актовый зал", 10, 1, ["it-support", "it-ai", "it-development"]),
            ("Экскурсия в компанию «ВР Концепт»: VR-разработка и 3D", "Профориентация", 2, 14, "Офис «ВР Концепт»", 10, 0, ["it-support", "it-ai", "it-development"]),
            ("Встреча с дизайнером: разбор портфолио", "Профориентация", 5, 17, "Дизайн-лаборатория колледжа", 10, None, ["creative-design", "creative-animation"]),
            ("Экскурсия и проба профессий в Stella Di Mosca", "Профориентация", 9, 15, "Stella Di Mosca", 10, 2, ["hospitality"]),
            ("Встреча с выпускниками: первый год работы после колледжа", "Профориентация", 20, 18, "Актовый зал", 10, None, all_track_slugs),
        ]
        events = []
        for title, cat, day, hour, place, reward, employer_index, track_slugs in ev_specs:
            start = today + timedelta(days=day, hours=hour)
            e = Event.objects.create(
                title=title, description=f"{title}. Познакомьтесь с профессиями, задайте вопросы и попробуйте себя в деле.\nНаграда за посещение — {reward} степов.",
                category=cats[cat], start=start, end=start + timedelta(hours=2), location=place, reward=reward,
                status=Event.Status.PUBLISHED, checkin_code=True, capacity=40 if day > 0 else None, created_by=admin,
            )
            if employer_index is not None:
                e.employer = employers[employer_index]
                e.registration_required = True
                e.save(update_fields=["employer", "registration_required"])
            e.tracks.set(Track.objects.filter(slug__in=track_slugs))
            events.append(e)
        for e in events[:3]:  # прошедшие — часть студентов посетила
            for u in rnd.sample(students, 12):
                mark_attended(e, u, "list", admin)

        for track in Track.objects.filter(is_active=True):
            related_event = next(e for e in events if e.tracks.filter(pk=track.pk).exists())
            TrackItem.objects.get_or_create(track=track, title=f"Попробовать направление: {track.title}", defaults={"kind": TrackItem.Kind.EVENT, "event": related_event, "required": True, "order": 1})

        mentor_tracks = list(Track.objects.filter(is_active=True)[:3])
        for mentor, track in zip([u for u in students if u.is_mentor][:3], mentor_tracks):
            mentor.mentor_tracks.add(track)
            MentorSlot.objects.get_or_create(mentor=mentor, track=track, topic=f"Вопросы по направлению {track.title}", start=now + timedelta(days=3),
                                             defaults={"duration": 45, "place": "Ауд. 204", "capacity": 5})

        t1 = Task.objects.create(title="Профессия рядом: мини-интервью со специалистом", description="Поговорите с действующим специалистом в выбранной сфере. Расскажите о его задачах, нужных навыках и о том, что вас заинтересовало.",
                                 kind=Task.Kind.MANUAL, status=Task.Status.PUBLISHED, deadline=now + timedelta(days=7), reward=20,
                                 allow_text=True, allow_files=True)
        t1.tracks.set(Track.objects.filter(slug__in=all_track_slugs))
        t2 = Task.objects.create(title="Первое собеседование: подготовка к стажировке", description="Проверьте, как подготовиться к первой встрече с работодателем. Нужно 60% правильных ответов.",
                                 kind=Task.Kind.AUTO, status=Task.Status.PUBLISHED, deadline=now + timedelta(days=14), reward=20, pass_percent=60, show_answers=True)
        t2.tracks.set(Track.objects.filter(slug__in=all_track_slugs))
        for i, (q, kind, opts, correct) in enumerate([
            ("Что полезно указать в резюме для первой стажировки?", "single", "Навыки и учебные проекты\nТолько желаемую зарплату\nОбщие фразы без примеров", "Навыки и учебные проекты"),
            ("О чём уместно спросить HR на первой встрече?", "single", "О задачах, требованиях и процессе отбора\nО личных данных коллег\nО том, как не проходить собеседование", "О задачах, требованиях и процессе отбора"),
            ("Как лучше понять, подходит ли профессия?", "single", "Попробовать небольшую рабочую задачу\nВыбирать только по названию\nНе узнавать о повседневных задачах", "Попробовать небольшую рабочую задачу"),
            ("Что взять с собой на экскурсию по предприятию?", "multi", "Подготовленные вопросы специалистам\nИнтерес к рабочим задачам\nОбязательный готовый трудовой договор", "Подготовленные вопросы специалистам\nИнтерес к рабочим задачам"),
            ("К кому обратиться за обратной связью о выбранном треке?", "single", "К наставнику или специалисту из этой сферы\nТолько к случайным пользователям в сети\nНи к кому", "К наставнику или специалисту из этой сферы"),
        ]):
            TaskQuestion.objects.create(task=t2, order=i, kind=kind, text=q, options=opts, correct=correct)
        t3 = Task.objects.create(title="Квест «Маршрут профессии»", description="Пройдите три шага знакомства с профессией: выясните, чем занимается HR, узнайте, что такое профпроба, и выберите, у кого попросить совета.",
                                 kind=Task.Kind.QUEST, status=Task.Status.PUBLISHED, deadline=now + timedelta(days=10), reward=20)
        t3.tracks.set(Track.objects.filter(slug__in=all_track_slugs))
        for i, (q, a) in enumerate([
            ("Как называют специалиста, который помогает компании находить сотрудников?", "HR"),
            ("Как называется короткая проба реальной рабочей задачи?", "Профпроба"),
            ("К кому можно обратиться за советом о карьере в выбранной сфере?", "Наставник"),
        ]):
            TaskQuestion.objects.create(task=t3, order=i, kind="text", text=q, correct=a)

        s = Survey.objects.create(kind=Survey.Kind.SURVEY, title="Какие направления и профессии тебе интересны?", description="Помоги подобрать полезные встречи, экскурсии и профессиональные пробы.", status=Survey.Status.PUBLISHED,
                                  closes_at=now + timedelta(days=10), reward=10)
        s.tracks.set(Track.objects.filter(slug__in=all_track_slugs))
        Question.objects.create(survey=s, order=1, kind="scale5", text="Насколько тебе интересны встречи с представителями профессий?")
        Question.objects.create(survey=s, order=2, kind="multi", text="Какие форматы профориентации ты хотел(а) бы посетить?", options="Экскурсии на предприятия\nВстречи с HR\nВстречи с действующими специалистами\nРазговоры со старшекурсниками и выпускниками\nПрофессиональные пробы")
        Question.objects.create(survey=s, order=3, kind="long", text="Какое направление или профессию ты хочешь изучить?", required=False)
        v = Survey.objects.create(kind=Survey.Kind.VOTE, title="Какое направление изучим на следующей встрече?", description="Выбери сферу для экскурсии или разговора с действующим специалистом.", status=Survey.Status.PUBLISHED,
                                  closes_at=now + timedelta(days=5), reward=10, results_visibility=Survey.Results.AFTER_VOTE)
        v.tracks.set(Track.objects.filter(slug__in=all_track_slugs))
        for i, t in enumerate(["ИТ и цифровые сервисы", "Дизайн и анимация", "Финансы", "Сервис, транспорт и гостиницы"]):
            VoteOption.objects.create(survey=v, order=i, title=t)

        # Каталог макетов и черновики товаров импортированы миграцией shop.0006_seed_merch_catalog.
        FundItem.objects.get_or_create(name="Велком-набор (стикерпак, пуллер, упаковка)", defaults={"kind": FundItem.Kind.WELCOME, "stock": 0})
        FundItem.objects.get_or_create(name="Поло наставника / преподавателя", defaults={"kind": FundItem.Kind.LOAN, "stock": 0})
        experience = Product.objects.create(title="Экскурсия в компанию «ВР Концепт» — ограниченные места", description="Место на экскурсию и встречу с командой работодателя. Покупка записывает на мероприятие.",
                                            kind=Product.Kind.EXPERIENCE, category=Product.Category.EXPERIENCE, event=events[4], price=40, per_user_limit=1, status=Product.Status.ON_SALE)
        ProductVariant.objects.create(product=experience, name="Место", stock=8)


        for i, (icon, title, desc, kind, cnt, rew) in enumerate([
            ("★", "Первое знакомство", "Посетить первое мероприятие", "events", 1, 0),
            ("⌂", "Исследователь предприятий", "Посетить три разных предприятия", "employers", 3, 0),
            ("◎", "Профиль интересов", "Пройти профдиагностику", "diagnostic", 1, 0),
            ("↗", "Путь выбран", "Выбрать основной профессиональный трек", "main_track", 1, 0),
            ("★", "Вклад в колледж", "Особый вклад в жизнь колледжа", "manual", 1, 0),
        ]):
            Achievement.objects.create(icon=icon, title=title, description=desc, kind=kind, count=cnt, reward=rew, order=i)
        # выдать достижения тем, кто уже посещал
        from achievements.services import check_achievements
        for u in students:
            check_achievements(u)

        self.stdout.write(self.style.SUCCESS("Готово. Демо-пользователи: admin, org, student1–student30; пароли заданы через окружение."))
