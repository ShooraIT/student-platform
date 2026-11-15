from django.db import migrations


TRACKS = [
    ("it-support", "ИТ · Поддержка", "Спокойно, я уже подключился."),
    ("it-ai", "ИТ · ИИ", "Будущее отвечает на запрос."),
    ("it-development", "ИТ · Разработка", "Сначала работало у меня."),
    ("creative-design", "Креатив · Дизайн", "Красиво — тоже функция."),
    ("creative-animation", "Креатив · Анимация", "Оживляю идеи."),
    ("finance", "Финансы", "Считаю на шаг вперёд."),
    ("cooks", "Повара", "Вкусно. Чётко. По таймингу."),
    ("transport-service", "Сервис на транспорте", "В пути всё под контролем."),
    ("hospitality", "Гостиницы", "Здесь гостю рады."),
]


def seed(apps, schema_editor):
    Track = apps.get_model("career", "Track")
    RouteStage = apps.get_model("career", "RouteStage")
    StageCondition = apps.get_model("career", "StageCondition")
    for order, (slug, title, tagline) in enumerate(TRACKS, 1):
        Track.objects.get_or_create(
            slug=slug,
            defaults={"title": title, "tagline": tagline, "description": "Профессиональное направление карьерного проекта 01:17.", "order": order},
        )
    stages = [
        ("Знакомство и адаптация", "Включись в жизнь колледжа", [("activities", 1)]),
        ("Профдиагностика", "Узнай свой профиль интересов", [("diagnostic", 1)]),
        ("Пробы в треках", "Попробуй активности в двух направлениях", [("tracks", 2)]),
        ("Выбор трека", "Отметь главное направление", [("main_track", 1)]),
        ("Портфолио и резюме", "Собери подтверждённый опыт и заполни резюме", [("portfolio", 1), ("resume", 1)]),
    ]
    for order, (title, description, conditions) in enumerate(stages, 1):
        stage, created = RouteStage.objects.get_or_create(order=order, defaults={"title": title, "description": description})
        if created:
            for kind, count in conditions:
                StageCondition.objects.create(stage=stage, kind=kind, count=count)


class Migration(migrations.Migration):
    dependencies = [("career", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
