from django.db import migrations, models
import django.db.models.deletion


ROLE_STARTERS = {
    "it-support": ("Специалист технической поддержки информационных систем", "Диагностировать обращения; настраивать рабочие места и доступы; документировать решения.", "Операционные системы, компьютерные сети, основы информационной безопасности, сервис-деск.", "Поиск причин неисправностей, настройка ПО, понятная коммуникация, ведение документации."),
    "it-ai": ("Специалист по интеграции решений с ИИ", "Подбирать ИИ-инструменты под задачи; подключать сервисы и API; проверять качество и безопасность результата.", "Основы машинного обучения и генеративного ИИ, работа с данными, API, приватность.", "Постановка задач, тестирование ответов, базовое программирование, оценка рисков."),
    "it-development": ("Веб-разработчик / разработчик программного обеспечения", "Создавать и поддерживать сайты и приложения; исправлять ошибки; работать с командой и документацией.", "Языки программирования, алгоритмы, базы данных, API, системы контроля версий.", "Разработка и отладка кода, чтение технических заданий, командная работа."),
    "creative-design": ("Графический / отраслевой дизайнер", "Исследовать задачу; разрабатывать визуальную концепцию; готовить макеты к публикации или производству.", "Композиция, типографика, цвет, основы визуальных коммуникаций и авторского права.", "Работа с графическими редакторами, прототипирование, презентация решений, приём обратной связи."),
    "creative-animation": ("Художник-аниматор", "Создавать раскадровки и анимацию; готовить материалы и сцены; участвовать в производственном цикле.", "Основы драматургии, композиция, движение, принципы 2D/3D-анимации.", "Раскадровка, работа с кадром и таймингом, цифровые инструменты, командное взаимодействие."),
    "finance": ("Специалист финансового направления", "Обрабатывать финансовые документы; готовить расчёты и сводки; помогать контролировать бюджет.", "Основы экономики, финансового учёта, документооборота и деловой этики.", "Точность расчётов, работа с таблицами, анализ данных, внимательность."),
    "cooks": ("Повар-кондитер", "Подготавливать продукты; готовить блюда и изделия по технологическим картам; соблюдать санитарные требования.", "Технология приготовления, сырьё, рецептуры, хранение и безопасность пищевых продуктов.", "Работа с оборудованием, точность рецептуры, организация рабочего места, соблюдение времени."),
    "transport-service": ("Специалист сервиса на транспорте", "Помогать пассажирам; координировать сервисные операции; решать типовые запросы во время поездки.", "Клиентский сервис, правила безопасности и основы транспортной логистики.", "Коммуникация, решение нестандартных ситуаций, внимательность, командная работа."),
    "hospitality": ("Специалист гостиничного сервиса", "Работать с бронированиями и размещением; отвечать на запросы гостей; координировать обслуживание.", "Гостиничные процессы, стандарты обслуживания, основы туризма и деловой коммуникации.", "Работа с системами бронирования, иностранный язык, решение запросов гостей, командная работа."),
}


def fill_role_starters(apps, schema_editor):
    Track = apps.get_model("career", "Track")
    for slug, values in ROLE_STARTERS.items():
        Track.objects.filter(slug=slug).update(
            position_title=values[0], duties=values[1], knowledge=values[2], skills=values[3]
        )

    Test = apps.get_model("career", "DiagTest")
    Scale = apps.get_model("career", "DiagScale")
    Question = apps.get_model("career", "DiagQuestion")
    Option = apps.get_model("career", "DiagOption")
    test, created = Test.objects.get_or_create(
        title="Роль в команде",
        defaults={"description": "Выбери варианты, которые ближе к твоему поведению в совместной работе. Результат — ориентир для рефлексии, не оценка.", "is_active": True},
    )
    if created:
        role_scales = {
            "Организатор": [
                "Помогаю распределить задачи и договориться о сроках.",
                "Слежу, чтобы команда двигалась к общей цели.",
                "Замечаю, если роли в команде не определены.",
                "Предлагаю план действий, когда непонятно, с чего начать.",
            ],
            "Исследователь": [
                "Собираю факты и проверяю предположения.",
                "Ищу причину проблемы, прежде чем предлагать решение.",
                "Сравниваю несколько вариантов и их последствия.",
                "Задаю уточняющие вопросы и ищу недостающие данные.",
            ],
            "Создатель": [
                "Предлагаю новые идеи и необычные подходы.",
                "Думаю, как превратить идею в понятный результат.",
                "Мне интересно создавать прототипы и пробовать новое.",
                "Представляю, каким может стать проект после доработки.",
            ],
            "Коммуникатор": [
                "Помогаю участникам услышать друг друга.",
                "Могу объяснить сложную мысль простыми словами.",
                "Поддерживаю участника, которому трудно включиться.",
                "Обсуждаю обратную связь так, чтобы команда могла двигаться дальше.",
            ],
        }
        scales = {name: Scale.objects.create(test=test, name=name, description="Роль может меняться в зависимости от задачи и состава команды.") for name in role_scales}
        for number in range(4):
            question = Question.objects.create(test=test, order=number + 1, text=[
                "Что ты обычно делаешь в начале общего проекта?",
                "Какой вклад тебе проще всего внести в работу группы?",
                "Что ты сделаешь, если команда столкнулась с трудностью?",
                "Какое признание за вклад в команду тебе ближе всего?",
            ][number])
            for role, texts in role_scales.items():
                Option.objects.create(question=question, text=texts[number], scale=scales[role], points=1)


class Migration(migrations.Migration):

    dependencies = [
        ("career", "0007_map_tracks_to_specialties"),
    ]

    operations = [
        migrations.AddField(
            model_name="track",
            name="position_title",
            field=models.CharField(blank=True, max_length=120, verbose_name="Пример должности"),
        ),
        migrations.AddField(
            model_name="track",
            name="duties",
            field=models.TextField(blank=True, verbose_name="Типовые задачи специалиста"),
        ),
        migrations.AddField(
            model_name="track",
            name="knowledge",
            field=models.TextField(blank=True, verbose_name="Необходимые знания"),
        ),
        migrations.AddField(
            model_name="track",
            name="skills",
            field=models.TextField(blank=True, verbose_name="Необходимые навыки"),
        ),
        migrations.CreateModel(
            name="Vacancy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=150, verbose_name="Должность / возможность")),
                ("description", models.TextField(blank=True, verbose_name="Описание")),
                ("location", models.CharField(blank=True, max_length=150, verbose_name="Место / формат")),
                ("url", models.URLField(blank=True, verbose_name="Ссылка")),
                ("closes_at", models.DateField(blank=True, null=True, verbose_name="Приём заявок до")),
                ("is_active", models.BooleanField(default=True, verbose_name="Показывать")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("employer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vacancies", to="career.employer", verbose_name="Работодатель")),
                ("track", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vacancies", to="career.track", verbose_name="Трек")),
            ],
            options={
                "verbose_name": "Вакансия / возможность",
                "verbose_name_plural": "Вакансии и возможности",
                "ordering": ["closes_at", "employer__name", "title"],
            },
        ),
        migrations.RunPython(fill_role_starters, migrations.RunPython.noop),
    ]
