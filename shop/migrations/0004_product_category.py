from django.db import migrations, models


def assign_existing_categories(apps, schema_editor):
    Product = apps.get_model("shop", "Product")
    Product.objects.filter(kind="experience").update(category="experience")
    Product.objects.filter(title__icontains="свитшот").update(category="clothing")


class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0003_product_tracks"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="category",
            field=models.CharField(
                choices=[("clothing", "Одежда"), ("accessories", "Аксессуары"), ("experience", "Впечатления")],
                default="accessories",
                max_length=16,
                verbose_name="Категория каталога",
            ),
        ),
        migrations.RunPython(assign_existing_categories, migrations.RunPython.noop),
    ]
