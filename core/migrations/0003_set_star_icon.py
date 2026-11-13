from django.db import migrations


def forwards(apps, schema_editor):
    apps.get_model("core", "SiteSettings").objects.filter(currency_icon="👣").update(currency_icon="✦")


class Migration(migrations.Migration):
    dependencies = [("core", "0002_currency_icon_star")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
