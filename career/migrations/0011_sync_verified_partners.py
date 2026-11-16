from django.db import migrations


IT_PARTNERS = [
    ("ВР Концепт", "Российский разработчик VR-движка и многопользовательской платформы. Студенты колледжа проходили практику по VR-разработке, программированию интерфейсов и 3D-моделированию."),
    ("Алгоритмика", "Партнёр колледжа в сфере информационных технологий. Актуальные практики и вакансии уточняются колледжем."),
    ("Технорэд", "Партнёр колледжа в сфере информационных технологий. Актуальные практики и вакансии уточняются колледжем."),
    ("Киберпротект", "Российский разработчик решений для резервного копирования и защиты данных; участвовал в создании новых ИТ-направлений колледжа."),
    ("Texel", "Партнёр колледжа в сфере информационных технологий. Актуальные практики и вакансии уточняются колледжем."),
    ("Лантер", "Партнёр колледжа в сфере информационных технологий. Актуальные практики и вакансии уточняются колледжем."),
    ("РДТЕХ", "Партнёр колледжа в сфере информационных технологий. Актуальные практики и вакансии уточняются колледжем."),
    ("Код безопасности", "Ключевой партнёр колледжа. Участвует в обновлении программ, мастер-классах, экскурсиях, практике и оценке квалификации выпускников."),
    ("Налог-Сервис", "Студенты встречались с представителями организации; обсуждались стажировки и задачи автоматизации налогообложения, разработки ПО и информационной безопасности."),
]


def sync_employers(apps, schema_editor):
    Employer = apps.get_model("career", "Employer")
    Track = apps.get_model("career", "Track")
    it_tracks = list(Track.objects.filter(slug__in=["it-support", "it-ai", "it-development"]))
    for name, description in IT_PARTNERS:
        employer, _ = Employer.objects.update_or_create(
            name=name,
            defaults={"industry": "Информационные технологии", "description": description, "is_active": True},
        )
        employer.tracks.set(it_tracks)

    hotel, _ = Employer.objects.update_or_create(
        name="Stella Di Mosca",
        defaults={
            "industry": "Гостиницы и гостеприимство",
            "description": "Обсуждение производственной практики и трудоустройства студентов гостиничного профиля.",
            "is_active": True,
        },
    )
    hotel.tracks.set(Track.objects.filter(slug="hospitality"))

    cooking_tracks = Track.objects.filter(slug="cooks")
    for name, description in [
        ("Мясо-Рыба", "База практики для студентов кулинарного направления; студенты знакомились с работой ресторанной кухни и возможностями оплачиваемой практики."),
        ("TORRO-GRILL", "Студенты проходили производственную практику и знакомились с работой ресторанной команды."),
        ("Team Academia", "Образовательная площадка HoReCa: студенты кулинарного направления участвовали в профессиональном интенсиве."),
    ]:
        employer, _ = Employer.objects.update_or_create(
            name=name,
            defaults={"industry": "Ресторанный бизнес и HoReCa", "description": description, "is_active": True},
        )
        employer.tracks.set(cooking_tracks)

    for name, description in [
        ("Artcourt Moscow Centre", "Студенты посещали отель, знакомились с работой номерного фонда и ресторана; публикация колледжа упоминает возможность практики и трудоустройства."),
    ]:
        employer, _ = Employer.objects.update_or_create(
            name=name,
            defaults={"industry": "Гостиничный бизнес", "description": description, "is_active": True},
        )
        employer.tracks.set(Track.objects.filter(slug="hospitality"))
    Employer.objects.filter(name__in=["ТехноПульс", "Студия «Форма»", "Отель «Полюс»"]).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [("career", "0010_expand_registry_specialties")]
    operations = [migrations.RunPython(sync_employers, migrations.RunPython.noop)]