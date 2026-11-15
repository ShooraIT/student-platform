"""Add career-project sample content to an existing local seed_demo database."""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from achievements.models import Achievement
from career.models import Employer, FundItem, MentorSlot, Track, TrackItem
from events.models import Category, Event
from shop.models import Product, ProductVariant
from surveys.models import Survey


class Command(BaseCommand):
    help = "Добавить карьерные демоданные к уже заполненной локальной демобазе"

    def handle(self, *args, **options):
        if not User.objects.filter(username="student1").exists():
            raise CommandError("Команда рассчитана на локальную базу после seed_demo")

        tracks = list(Track.objects.filter(is_active=True))
        if len(tracks) != 9:
            raise CommandError("Сначала примените миграции стартовых треков")
        by_slug = {track.slug: track for track in tracks}
        companies = [
            ("ТехноПульс", "ИТ", "Поддержка цифровых сервисов и инженерные команды.", ["it-support", "it-ai", "it-development", "finance"]),
            ("Студия «Форма»", "Креатив", "Дизайн, анимация и визуальные коммуникации.", ["creative-design", "creative-animation"]),
            ("Отель «Полюс»", "Гостиницы и сервис", "Гостиничный сервис и работа с гостями.", ["cooks", "transport-service", "hospitality"]),
        ]
        employers = []
        for name, industry, description, slugs in companies:
            employer, _ = Employer.objects.get_or_create(name=name, defaults={"industry": industry, "description": description})
            employer.industry, employer.description, employer.is_active = industry, description, True
            employer.save(update_fields=["industry", "description", "is_active"])
            employer.tracks.set(by_slug[s] for s in slugs)
            employers.append(employer)

        now = timezone.now()
        event = Event.objects.filter(status=Event.Status.PUBLISHED, start__gt=now, employer=employers[0]).order_by("start").first()
        if event is None:
            category, _ = Category.objects.get_or_create(name="Профориентация", defaults={"color": "#1d1f27"})
            event = Event.objects.create(
                title="Встреча с ИТ-командой ТехноПульс",
                description="Знакомство с работодателем и проба профессиональных задач.",
                category=category, employer=employers[0], start=now + timedelta(days=14),
                end=now + timedelta(days=14, hours=2), location="Коворкинг колледжа",
                registration_required=True, registration_deadline=now + timedelta(days=13),
                capacity=20, reward=10, status=Event.Status.PUBLISHED,
            )
        for track in tracks:
            TrackItem.objects.get_or_create(
                track=track, title=f"Демоактивность: {track.title}",
                defaults={"kind": TrackItem.Kind.EVENT, "event": event, "required": True, "order": 1},
            )

        seniors = User.objects.filter(role=User.Role.STUDENT, expelled=False, group__course__gte=2, group__course__lte=4).order_by("id")
        for mentor, track in zip(seniors[:3], tracks[:3]):
            if not mentor.is_mentor:
                mentor.is_mentor = True
                mentor.save(update_fields=["is_mentor"])
            mentor.mentor_tracks.add(track)
            has_upcoming = MentorSlot.objects.filter(mentor=mentor, track=track, is_cancelled=False, start__gt=now).exists()
            if not has_upcoming:
                MentorSlot.objects.create(
                    mentor=mentor, track=track, topic=f"Знакомство с треком «{track.title}»",
                    start=now + timedelta(days=7), duration=45, place="Ауд. 204", capacity=5,
                )

        for product in Product.objects.filter(status=Product.Status.ON_SALE, title__icontains="линейки"):
            product.tracks.set(tracks)
        patch = Product.objects.filter(title="Патч на велкро").first()
        if patch:
            patch.kind, patch.price, patch.status = Product.Kind.REWARD, 0, Product.Status.OFF
            patch.save(update_fields=["kind", "price", "status"])
            ProductVariant.objects.update_or_create(product=patch, name="—", defaults={"stock": 30})
        backpack, _ = Product.objects.get_or_create(
            title="Рюкзак 01:17",
            defaults={"description": "Только награда колледжа.", "price": 0, "kind": Product.Kind.REWARD, "status": Product.Status.OFF},
        )
        backpack.kind, backpack.price, backpack.status = Product.Kind.REWARD, 0, Product.Status.OFF
        backpack.save(update_fields=["kind", "price", "status"])
        ProductVariant.objects.update_or_create(product=backpack, name="—", defaults={"stock": 6})

        experience, _ = Product.objects.get_or_create(
            title="Встреча с ИТ-командой — ограниченные места",
            defaults={"description": "Покупка места записывает на встречу с работодателем.", "event": event,
                      "price": 40, "kind": Product.Kind.EXPERIENCE, "per_user_limit": 1, "status": Product.Status.ON_SALE},
        )
        experience.event, experience.kind, experience.price = event, Product.Kind.EXPERIENCE, 40
        experience.per_user_limit, experience.status = 1, Product.Status.ON_SALE
        experience.save(update_fields=["event", "kind", "price", "per_user_limit", "status"])
        ProductVariant.objects.update_or_create(product=experience, name="Место", defaults={"stock": 8})

        FundItem.objects.get_or_create(name="Велком-набор (стикерпак, пуллер, упаковка)", defaults={"kind": FundItem.Kind.WELCOME, "stock": 1500})
        FundItem.objects.get_or_create(name="Поло наставника / преподавателя", defaults={"kind": FundItem.Kind.LOAN, "stock": 30})

        badges = [
            ("Первое знакомство", "Посетить первое мероприятие", Achievement.Kind.EVENTS, 1),
            ("Исследователь предприятий", "Посетить три разных предприятия", Achievement.Kind.EMPLOYERS, 3),
            ("Профиль интересов", "Пройти профдиагностику", Achievement.Kind.DIAGNOSTIC, 1),
            ("Путь выбран", "Выбрать основной профессиональный трек", Achievement.Kind.MAIN_TRACK, 1),
            ("Первый проект", "Получить принятый проект в портфолио", Achievement.Kind.TASKS, 1),
        ]
        for order, (title, description, kind, count) in enumerate(badges, 1):
            Achievement.objects.update_or_create(
                title=title, defaults={"description": description, "kind": kind, "count": count, "reward": 0,
                                       "is_active": True, "order": order},
            )
        valid_kinds = [choice for choice, _ in Achievement.Kind.choices]
        Achievement.objects.exclude(kind__in=valid_kinds).update(is_active=False)
        Survey.objects.filter(reward__gt=0).update(reward=10)
        for title in ("Фото с субботника", "Викторина: история колледжа", "Квест «Тайны корпуса»"):
            # The seed demo's completed project tasks use the common 20-step rate.
            from assignments.models import Task

            Task.objects.filter(title=title).update(reward=20)
        Event.objects.filter(reward__gt=10).update(reward=10)
        self.stdout.write(self.style.SUCCESS("Карьерные демоданные обновлены."))
