import json
from pathlib import Path

from django.conf import settings
from django.db import migrations


STICKER_IDS = {"sticker-3d", "sticker-holographic"}


def add_sticker_products(apps, schema_editor):
    Product = apps.get_model("shop", "Product")
    ProductVariant = apps.get_model("shop", "ProductVariant")
    manifest_path = Path(settings.BASE_DIR) / "static" / "shop" / "merch" / "catalog.json"
    with manifest_path.open(encoding="utf-8") as source:
        manifest = json.load(source)

    for order, item in enumerate(manifest["items"], start=1):
        if item["id"] not in STICKER_IDS:
            continue
        product, created = Product.objects.get_or_create(
            title=item["title"],
            defaults={
                "kind": "merch",
                "category": item["category"],
                "description": item["label"] + ". Концептуальный макет; цена указана ориентировочно.",
                "price": item["price"],
                "asset_path": item["image"],
                "status": "draft",
                "per_user_limit": None,
                "order": order,
            },
        )
        if not created:
            product.asset_path = item["image"]
            if not product.price:
                product.price = item["price"]
            product.save(update_fields=["asset_path", "price"])
        ProductVariant.objects.get_or_create(product=product, name="—", defaults={"stock": 0})


class Migration(migrations.Migration):
    dependencies = [("shop", "0007_merch_prices_and_catalog_extras")]

    operations = [migrations.RunPython(add_sticker_products, migrations.RunPython.noop)]
