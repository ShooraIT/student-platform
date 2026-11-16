import json
from pathlib import Path

from django.conf import settings
from django.db import migrations


def seed_merch_catalog(apps, schema_editor):
    Product = apps.get_model("shop", "Product")
    ProductVariant = apps.get_model("shop", "ProductVariant")
    Track = apps.get_model("career", "Track")
    FundItem = apps.get_model("career", "FundItem")
    manifest_path = Path(settings.BASE_DIR) / "static" / "shop" / "merch" / "catalog.json"
    with manifest_path.open(encoding="utf-8") as source:
        manifest = json.load(source)

    tracks = {track.slug: track for track in Track.objects.all()}
    for item in manifest["items"]:
        is_reward = item["type"] == "reward"
        product, created = Product.objects.get_or_create(
            title=item["title"],
            defaults={
                "kind": "reward" if is_reward else "merch",
                "category": item["category"],
                "description": (
                    "Награда колледжа. Выдаётся администратором."
                    if is_reward else
                    "Концептуальный макет из коллекции 01:17. Перед публикацией укажите согласованную цену и квоту."
                    + (" Макет этого варианта ещё не добавлен в папку." if not item["image"] else "")
                ),
                "price": 0,
                "asset_path": item["image"],
                "status": "off" if is_reward else "draft",
                "per_user_limit": None,
            },
        )
        if not created and not product.asset_path and item["image"]:
            product.asset_path = item["image"]
            product.save(update_fields=["asset_path"])
        if item.get("track") and item["track"] in tracks:
            product.tracks.add(tracks[item["track"]])
        ProductVariant.objects.get_or_create(product=product, name="—", defaults={"stock": 0})

    for supply in manifest.get("supplies", []):
        kind = "welcome" if supply["kind"] == "welcome" else "loan"
        FundItem.objects.get_or_create(
            name=supply["title"],
            defaults={"kind": kind, "stock": 0, "asset_path": supply["image"]},
        )


def unseed_merch_catalog(apps, schema_editor):
    # Keep seeded catalog rows when rolling back; admins may already have configured them.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0005_product_asset_path"),
        ("career", "0009_funditem_asset_path"),
    ]

    operations = [migrations.RunPython(seed_merch_catalog, unseed_merch_catalog)]
