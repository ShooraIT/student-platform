from django.db import migrations


TRACK_SPECIALTIES = {
    "it-support": "09.02.07,09.02.12",
    "it-ai": "09.02.13",
    "it-development": "09.02.07,09.02.09,09.02.11",
    "creative-design": "54.01.20,54.02.01",
    "creative-animation": "55.02.02",
    "finance": "38.02.06",
    "cooks": "43.02.15",
    "transport-service": "43.02.06",
    "hospitality": "43.02.16",
}


def map_specialties(apps, schema_editor):
    Track = apps.get_model("career", "Track")
    for slug, codes in TRACK_SPECIALTIES.items():
        Track.objects.filter(slug=slug).update(specialties=codes)


class Migration(migrations.Migration):
    dependencies = [("career", "0006_alter_externalachievement_file")]

    operations = [migrations.RunPython(map_specialties, migrations.RunPython.noop)]
