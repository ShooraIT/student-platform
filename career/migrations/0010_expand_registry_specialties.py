from django.db import migrations


def expand_it_support_specialties(apps, schema_editor):
    Track = apps.get_model("career", "Track")
    Track.objects.filter(slug="it-support").update(
        specialties="09.02.01,09.02.06,09.02.07,09.02.12,11.02.15"
    )


class Migration(migrations.Migration):
    dependencies = [("career", "0009_funditem_asset_path")]

    operations = [migrations.RunPython(expand_it_support_specialties, migrations.RunPython.noop)]
