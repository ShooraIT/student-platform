from django.db import migrations


QUESTIONS = [
    ("Какую задачу ты бы выбрал для учебного проекта?", [
        ("Помочь человеку разобраться с техникой", "people", {"people": 3, "service": 1}),
        ("Найти закономерность в данных и автоматизировать процесс", "analysis", {"analysis": 3, "service": 1}),
        ("Придумать визуальную концепцию и показать её команде", "creative", {"creative": 3, "people": 1}),
        ("Организовать работу и сделать результат удобным для людей", "service", {"service": 3, "people": 1}),
    ]),
    ("Что тебе интереснее изучать?", [
        ("Как устроены устройства и почему они ломаются", "people", {"people": 2, "analysis": 1}),
        ("Как обучаются модели и принимают решения программы", "analysis", {"analysis": 3}),
        ("Как цвет, движение и форма влияют на впечатление", "creative", {"creative": 3}),
        ("Как устроен хороший сервис и работа с гостями", "service", {"service": 3, "people": 1}),
    ]),
    ("В команде ты чаще…", [
        ("Поддерживаешь тех, кому нужна помощь", "people", {"people": 3, "service": 1}),
        ("Разбираешь сложность на логические шаги", "analysis", {"analysis": 3}),
        ("Предлагаешь идеи и собираешь образ результата", "creative", {"creative": 3}),
        ("Следишь, чтобы всё было согласовано и вовремя", "service", {"service": 3}),
    ]),
    ("Какой результат приносит больше удовлетворения?", [
        ("Человек смог сам решить проблему", "people", {"people": 3, "service": 1}),
        ("Система стала точнее или быстрее", "analysis", {"analysis": 3}),
        ("Идея превратилась в готовый визуальный продукт", "creative", {"creative": 3}),
        ("Гость или клиент получил отличный опыт", "service", {"service": 3, "people": 1}),
    ]),
    ("Что ты готов тренировать дольше всего?", [
        ("Общение и решение пользовательских задач", "people", {"people": 3}),
        ("Математику, логику и работу с данными", "analysis", {"analysis": 3}),
        ("Рисунок, монтаж и создание образов", "creative", {"creative": 3}),
        ("Организацию процессов и внимательность к деталям", "service", {"service": 3}),
    ]),
]


def seed(apps, schema_editor):
    Test = apps.get_model("career", "DiagTest")
    Scale = apps.get_model("career", "DiagScale")
    Question = apps.get_model("career", "DiagQuestion")
    Option = apps.get_model("career", "DiagOption")
    Weight = apps.get_model("career", "DiagOptionWeight")
    Track = apps.get_model("career", "Track")
    test, created = Test.objects.get_or_create(title="Профиль интересов 01:17", defaults={"description": "Ответь на вопросы и получи 2–3 направления для знакомства.", "is_active": True})
    if not created or test.questions.exists():
        return
    scale_tracks = {
        "people": ["it-support", "hospitality"],
        "analysis": ["it-ai", "it-development", "finance"],
        "creative": ["creative-design", "creative-animation"],
        "service": ["cooks", "transport-service", "hospitality"],
    }
    scales = {}
    for name, title in [("people", "Помощь людям"), ("analysis", "Аналитика и логика"), ("creative", "Креатив и визуал"), ("service", "Сервис и организация")]:
        scale = Scale.objects.create(test=test, name=title, description="Показатель интереса, а не оценка способностей.")
        scale.tracks.set(Track.objects.filter(slug__in=scale_tracks[name]))
        scales[name] = scale
    for number, (text, options) in enumerate(QUESTIONS, 1):
        question = Question.objects.create(test=test, text=text, order=number)
        for answer, main, weights in options:
            option = Option.objects.create(question=question, text=answer, scale=scales[main], points=weights[main])
            Weight.objects.bulk_create([Weight(option=option, scale=scales[key], points=value) for key, value in weights.items()])


class Migration(migrations.Migration):
    dependencies = [("career", "0004_diagoptionweight"), ("career", "0003_track_cover")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
