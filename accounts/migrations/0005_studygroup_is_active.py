from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_studygroup_specialty_name")]

    operations = [
        migrations.AddField(
            model_name="studygroup",
            name="is_active",
            field=models.BooleanField(default=True, verbose_name="В актуальном реестре"),
        ),
    ]
