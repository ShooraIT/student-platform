"""Демо-данные для показа и проверки. НЕ запускать на боевой базе.

python manage.py seed_demo
Создаёт: суперадмина admin / admin12345, 3 группы, 30 студентов (пароль student123, без смены пароля),
мероприятия, задания, опрос, голосование, товары, карьерные треки и достижения.
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import StudyGroup, User
from achievements.models import Achievement
from assignments.models import Task, TaskQuestion
from career.models import Employer, FundItem, MentorSlot, Track, TrackItem
from events.models import Category, Event
from events.services import mark_attended
from shop.models import Product, ProductVariant
from surveys.models import Question, Survey, VoteOption

LAST = ["Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров", "Соколов", "Михайлов", "Новиков", "Фёдоров"]
FIRST_M = ["Артём", "Максим", "Иван", "Даниил", "Кирилл"]
FIRST_F = ["Анна", "Мария", "Софья", "Алиса", "Виктория"]


class Command(BaseCommand):
    help = "Заполнить базу демо-данными"

    @transaction.atomic
    def handle(self, *args, **opts):
        if User.objects.filter(username="admin").exists():
            self.stdout.write("Демо-данные уже есть")
            return
        rnd = random.Random(1)
        now = timezone.now()
        admin = User.objects.create_user("admin", password="admin12345", first_name="Анна", last_name="Админова", role=User.Role.SUPERADMIN)
        User.objects.create_user("org", password="org12345", first_name="Олег", last_name="Организаторов", role=User.Role.ADMIN)

        groups = [StudyGroup.objects.create(name=n, course=c, specialty=s) for n, c, s in
                  [("СИП-11", 1, "09.02.07"), ("СИП-21", 2, "09.02.07"), ("СЭС-31", 3, "13.02.11")]]
        students = []
        for i in range(30):
            female = i % 2 == 0
            last = LAST[i % 10] + ("а" if female else "")
            first = (FIRST_F if female else FIRST_M)[i % 5]
            u = User.objects.create_user(f"student{i + 1}", password="student123", first_name=first, last_name=last,
                                         group=groups[i % 3], role=User.Role.STUDENT,
                                         is_mentor=(i % 3 in (1, 2) and i < 12))
            students.append(u)

        cats = {n: Category.objects.create(name=n, color=c) for n, c in
                [("Спорт", "#2e7d4f"), ("Творчество", "#cb563d"), ("Учёба", "#f1a627"), ("Волонтёрство", "#cb563d"), ("Профориентация", "#1d1f27")]}
        employers = [
            Employer.objects.create(name="ТехноПульс", industry="ИТ", description="Поддержка цифровых сервисов и инженерные команды."),
            Employer.objects.create(name="Студия «Форма»", industry="Креатив", description="Дизайн, анимация и визуальные коммуникации."),
            Employer.objects.create(name="Отель «Полюс»", industry="Гостиницы и сервис", description="Гостиничный сервис и работа с гостями."),
        ]
        employers[0].tracks.set(Track.objects.filter(slug__in=["it-support", "it-ai", "it-development", "finance"]))
        employers[1].tracks.set(Track.objects.filter(slug__in=["creative-design", "creative-animation"]))
        employers[2].tracks.set(Track.objects.filter(slug__in=["cooks", "transport-service", "hospitality"]))
        today = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
        ev_specs = [
            ("Турнир по настольному теннису", "Спорт", -10, 15, "Спортзал", 10),
            ("Мастер-класс по скетчингу", "Творчество", -5, 16, "Ауд. 204", 10),
            ("Хакатон «Цифровой колледж»", "Учёба", -2, 10, "Коворкинг", 10),
            ("Субботник во дворе колледжа", "Волонтёрство", 0, timezone.localtime(now).hour, "Двор колледжа", 10),
            ("Встреча с выпускниками-разработчиками", "Профориентация", 2, 14, "Актовый зал", 10),
            ("Квиз «Своя игра»", "Учёба", 5, 17, "Ауд. 301", 10),
            ("Футбольный матч СИП vs СЭС", "Спорт", 9, 15, "Стадион", 10),
            ("Концерт ко Дню студента", "Творчество", 20, 18, "Актовый зал", 10),
        ]
        events = []
        for title, cat, day, hour, place, reward in ev_specs:
            start = today + timedelta(days=day, hours=hour)
            e = Event.objects.create(
                title=title, description=f"{title}. Приходите — будет интересно!\nНаграда за посещение — {reward} степов.",
                category=cats[cat], start=start, end=start + timedelta(hours=2), location=place, reward=reward,
                status=Event.Status.PUBLISHED, checkin_code=True, capacity=40 if day > 0 else None, created_by=admin,
            )
            events.append(e)
        events[4].employer = employers[0]
        events[4].registration_required = True
        events[4].save(update_fields=["employer", "registration_required"])
        for e in events[:3]:  # прошедшие — часть студентов посетила
            for u in rnd.sample(students, 12):
                mark_attended(e, u, "list", admin)

        for i, track in enumerate(Track.objects.filter(is_active=True)):
            TrackItem.objects.get_or_create(track=track, title=f"Попробовать направление: {track.title}", defaults={"kind": TrackItem.Kind.EVENT, "event": events[i % len(events)], "required": True, "order": 1})

        mentor_tracks = list(Track.objects.filter(is_active=True)[:3])
        for mentor, track in zip([u for u in students if u.is_mentor][:3], mentor_tracks):
            mentor.mentor_tracks.add(track)
            MentorSlot.objects.get_or_create(mentor=mentor, track=track, topic=f"Вопросы по направлению {track.title}", start=now + timedelta(days=3),
                                             defaults={"duration": 45, "place": "Ауд. 204", "capacity": 5})

        t1 = Task.objects.create(title="Фото с субботника", description="Пришлите фото с субботника, где видно вас и результат работы.",
                                 kind=Task.Kind.MANUAL, status=Task.Status.PUBLISHED, deadline=now + timedelta(days=7), reward=20,
                                 allow_text=True, allow_files=True)
        t2 = Task.objects.create(title="Викторина: история колледжа", description="5 вопросов о колледже. Нужно 60% правильных.",
                                 kind=Task.Kind.AUTO, status=Task.Status.PUBLISHED, deadline=now + timedelta(days=14), reward=20, pass_percent=60, show_answers=True)
        for i, (q, kind, opts, correct) in enumerate([
            ("В каком году основан колледж?", "single", "1945\n1961\n1980", "1961"),
            ("Как называется студенческая валюта платформы?", "text", "", "степы\nстепы\nстеп"),
            ("Какие направления есть в колледже?", "multi", "Программирование\nЭнергетика\nМедицина", "Программирование\nЭнергетика"),
            ("Сколько этажей в главном корпусе?", "single", "3\n4\n5", "4"),
            ("Столица России?", "text", "", "Москва"),
        ]):
            TaskQuestion.objects.create(task=t2, order=i, kind=kind, text=q, options=opts, correct=correct)
        t3 = Task.objects.create(title="Квест «Тайны корпуса»", description="Найдите коды, спрятанные в корпусе. Каждый следующий шаг откроется после правильного ответа.",
                                 kind=Task.Kind.QUEST, status=Task.Status.PUBLISHED, deadline=now + timedelta(days=10), reward=20)
        for i, (q, a) in enumerate([("Код на доске объявлений у входа", "СТАРТ"), ("Код в библиотеке на 2 этаже", "КНИГА"), ("Код у кабинета директора", "ФИНИШ")]):
            TaskQuestion.objects.create(task=t3, order=i, kind="text", text=q, correct=a)

        s = Survey.objects.create(kind=Survey.Kind.SURVEY, title="Как вам мероприятия этого месяца?", status=Survey.Status.PUBLISHED,
                                  closes_at=now + timedelta(days=10), reward=10)
        Question.objects.create(survey=s, order=1, kind="scale5", text="Оцените мероприятия в целом")
        Question.objects.create(survey=s, order=2, kind="multi", text="Что хотите чаще?", options="Спорт\nТворчество\nХакатоны\nЭкскурсии")
        Question.objects.create(survey=s, order=3, kind="long", text="Ваши предложения", required=False)
        v = Survey.objects.create(kind=Survey.Kind.VOTE, title="Выбираем тему новогоднего вечера", status=Survey.Status.PUBLISHED,
                                  closes_at=now + timedelta(days=5), reward=10, results_visibility=Survey.Results.AFTER_VOTE)
        for i, t in enumerate(["Киберпанк", "Голливуд", "Зимняя сказка", "80-е"]):
            VoteOption.objects.create(survey=v, order=i, title=t)

        # Каталог по смете проекта 01:17 (базовый сценарий): цены в баллах и квоты обмена.
        # Девять профессиональных линеек: у шопера, прямоугольного значка и ремувки своя фраза.
        lines = [
            ("ИТ · Поддержка", "Спокойно, я уже подключился.", "Перезагрузка — тоже план", "СИГНАЛ ЕСТЬ"),
            ("ИТ · ИИ", "Думаю слоями.", "Обучаюсь на ходу", "ЕЩЁ ЭПОХУ"),
            ("ИТ · Разработка", "Ещё один коммит — и спать.", "Работает. Не трогай.", "В ПРОЦЕССЕ"),
            ("Креатив · Дизайн", "Ещё на пиксель левее.", "Есть ещё вариант", "ВНЕ СЕТКИ"),
            ("Креатив · Анимация", "Сейчас всё оживёт.", "Характер в движении", "МЕЖДУ КАДРАМИ"),
            ("Финансы", "Люблю, когда всё сходится.", "Считаю на перспективу", "БАЛАНС НАЙДЕН"),
            ("Повара", "Мой почерк пробуют на вкус.", "Довожу до вкуса", "ЩЕПОТКА ХАРАКТЕРА"),
            ("Сервис на транспорте", "Поехали. Об остальном позабочусь.", "Сервис без остановок", "ХОРОШЕГО ПУТИ"),
            ("Гостиницы", "Уют начинается с меня.", "Здесь вам рады", "ВСЁ ДЛЯ ГОСТЯ"),
        ]

        def phrases(i):
            return "\n".join(f"{ln[0]} — «{ln[i]}»" for ln in lines)

        line_names = [ln[0] for ln in lines]
        tracks_by_title = {t.title: t for t in Track.objects.filter(is_active=True)}
        for title, price, desc, variants, limit in [
            ("Круглый значок 01:17", 20, "Значок с логотипом проекта.", [("—", 72)], None),
            ("Ремувка профессиональной линейки", 60, "Ремувка с фразой своего направления. Выберите линейку:\n" + phrases(3),
             [(n, 5) for n in line_names], 2),
            ("Прямоугольный значок линейки", 70, "Печатный значок с фразой направления:\n" + phrases(2),
             [(n, 4) for n in line_names], 2),
            ("Патч на велкро", 0, "Патч 01:17 — только как награда колледжа.", [("—", 30)], 1),
            ("Шопер профессиональной линейки", 440, "Хлопковый шопер с фразой направления:\n" + phrases(1),
             [(n, 2) for n in line_names[:6]] + [(n, 1) for n in line_names[6:]], 1),
            ("Свитшот 01:17", 690, "Свитшот с нанесением. Количество ограничено.", [("S", 1), ("M", 2), ("L", 2), ("XL", 1)], 1),
        ]:
            reward_only = title == "Патч на велкро"
            p = Product.objects.create(title=title, description=desc, price=price, per_user_limit=limit,
                                       kind=Product.Kind.REWARD if reward_only else Product.Kind.MERCH,
                                       status=Product.Status.OFF if reward_only else Product.Status.ON_SALE)
            if "линейки" in title.lower():
                p.tracks.set(tracks_by_title[n] for n in line_names if n in tracks_by_title)
            for n, st in variants:
                ProductVariant.objects.create(product=p, name=n, stock=st)

        backpack = Product.objects.create(title="Рюкзак 01:17", description="Только награда колледжа.", price=0,
                                          kind=Product.Kind.REWARD, status=Product.Status.OFF)
        ProductVariant.objects.create(product=backpack, name="—", stock=6)
        FundItem.objects.get_or_create(name="Велком-набор (стикерпак, пуллер, упаковка)", defaults={"kind": FundItem.Kind.WELCOME, "stock": 1500})
        FundItem.objects.get_or_create(name="Поло наставника / преподавателя", defaults={"kind": FundItem.Kind.LOAN, "stock": 30})
        experience = Product.objects.create(title="Встреча с ИТ-командой — ограниченные места", description="Место на встречу с работодателем. Покупка записывает на мероприятие.",
                                            kind=Product.Kind.EXPERIENCE, event=events[4], price=40, per_user_limit=1, status=Product.Status.ON_SALE)
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

        self.stdout.write(self.style.SUCCESS("Готово. Вход: admin / admin12345 (суперадмин), student1 / student123 (студент)"))
