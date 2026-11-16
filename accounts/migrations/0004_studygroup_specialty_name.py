from django.db import migrations, models


SPECIALTY_NAMES = {
    "09.02.01": "Компьютерные системы и комплексы",
    "09.02.06": "Сетевое и системное администрирование",
    "09.02.07": "Информационные системы и программирование",
    "09.02.09": "Веб-разработка",
    "09.02.11": "Разработка и управление программным обеспечением",
    "09.02.12": "Техническая эксплуатация и сопровождение информационных систем",
    "09.02.13": "Интеграция решений с применением технологий искусственного интеллекта",
    "11.02.15": "Инфокоммуникационные сети и системы связи",
    "21.02.04": "Землеустройство",
    "38.02.06": "Финансы",
    "43.02.06": "Сервис на транспорте (по видам транспорта)",
    "43.02.15": "Поварское и кондитерское дело",
    "43.02.16": "Туризм и гостеприимство",
    "54.01.20": "Графический дизайн",
    "54.02.01": "Дизайн",
    "55.02.02": "Анимация и анимационное кино",
}


def backfill_names(apps, schema_editor):
    StudyGroup = apps.get_model("accounts", "StudyGroup")
    for code, name in SPECIALTY_NAMES.items():
        StudyGroup.objects.filter(specialty=code, specialty_name="").update(specialty_name=name)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_user_mentor_tracks")]

    operations = [
        migrations.AddField(
            model_name="studygroup",
            name="specialty_name",
            field=models.CharField(blank=True, max_length=150, verbose_name="Название специальности"),
        ),
        migrations.RunPython(backfill_names, migrations.RunPython.noop),
    ]
