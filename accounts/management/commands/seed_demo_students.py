import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import StudyGroup, User


DEMO_GROUPS = (
    # Реальные группы выбраны из реестра БУП 2026/2027.
    ("it-support", "ИС-116", 1, "09.02.12", "Техническая эксплуатация и сопровождение информационных систем"),
    ("it-ai", "ИИ-116", 1, "09.02.13", "Интеграция решений с применением технологий искусственного интеллекта"),
    ("it-development", "ПО-116", 1, "09.02.11", "Разработка и управление программным обеспечением"),
    ("creative-design", "Дизайн-ДЕМО", 1, "54.01.20", "Графический дизайн (демо)"),
    ("creative-animation", "Анимация-ДЕМО", 1, "55.02.02", "Анимация и анимационное кино (демо)"),
    ("finance", "26ФН-01", 1, "38.02.06", "Финансы"),
    ("cooks", "26ПКД-02", 1, "43.02.15", "Поварское и кондитерское дело"),
    ("transport-service", "26СТ-07", 1, "43.02.06", "Сервис на транспорте (по видам транспорта)"),
    ("hospitality", "26ТГ-06", 1, "43.02.16", "Туризм и гостеприимство"),
)

LAST_NAMES = [
    "Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров", "Соколов", "Михайлов",
    "Новиков", "Фёдоров", "Морозов", "Волков", "Алексеев", "Лебедев", "Семёнов", "Егоров",
    "Павлов", "Козлов", "Степанов", "Николаев", "Орлов", "Андреев", "Макаров", "Захаров",
    "Зайцев", "Соловьёв", "Борисов", "Яковлев", "Григорьев", "Романов",
]
FIRST_NAMES = [
    "Артём", "Анна", "Максим", "Мария", "Иван", "Софья", "Даниил", "Алиса", "Кирилл", "Виктория",
    "Михаил", "Полина", "Александр", "Елизавета", "Дмитрий", "Варвара", "Матвей", "Анастасия",
    "Роман", "Дарья", "Никита", "Ксения", "Егор", "Арина", "Лев", "Милана", "Тимофей", "Ева",
    "Илья", "Василиса",
]


class Command(BaseCommand):
    help = "Создать или обновить демо-набор: 30 синтетических студентов на каждый карьерный трек"

    def add_arguments(self, parser):
        parser.add_argument("--students-per-group", type=int, default=30)
        parser.add_argument("--reset-passwords", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.environ.get("DEMO_STUDENT_PASSWORD")
        if not password:
            raise CommandError("Перед запуском задайте DEMO_STUDENT_PASSWORD.")
        amount = options["students_per_group"]
        if amount < 1 or amount > 100:
            raise CommandError("Для демо можно создать от 1 до 100 студентов в группе.")

        created = updated = 0
        for track_slug, group_name, course, specialty, specialty_name in DEMO_GROUPS:
            group, _ = StudyGroup.objects.update_or_create(
                name=group_name,
                defaults={
                    "course": course,
                    "specialty": specialty,
                    "specialty_name": specialty_name,
                    "is_active": True,
                },
            )
            for number in range(1, amount + 1):
                username = f"demo-{track_slug}-{number:02d}"
                user, was_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "first_name": FIRST_NAMES[(number - 1) % len(FIRST_NAMES)],
                        "last_name": LAST_NAMES[(number - 1) % len(LAST_NAMES)],
                        "group": group,
                        "role": User.Role.STUDENT,
                        "balance": 70 + (number % 8) * 10,
                    },
                )
                if was_created:
                    user.set_password(password)
                    user.save(update_fields=["password"])
                    created += 1
                else:
                    update_fields = []
                    if user.group_id != group.pk:
                        user.group = group
                        update_fields.append("group")
                    if options["reset_passwords"]:
                        user.set_password(password)
                        update_fields.append("password")
                    if update_fields:
                        user.save(update_fields=update_fields)
                        updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Демо-набор: {len(DEMO_GROUPS)} групп по {amount}; "
            f"{created} студентов добавлено, {updated} привязок обновлено."
        ))
