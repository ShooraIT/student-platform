import json
from pathlib import Path

from django.conf import settings
from django.db import migrations


def set_estimate_prices_and_extras(apps, schema_editor):
    Product = apps.get_model("shop", "Product")
    ProductVariant = apps.get_model("shop", "ProductVariant")
    Track = apps.get_model("career", "Track")
    manifest_path = Path(settings.BASE_DIR) / "static" / "shop" / "merch" / "catalog.json"
    with manifest_path.open(encoding="utf-8") as source:
        manifest = json.load(source)

    tracks = {track.slug: track for track in Track.objects.all()}
    for order, item in enumerate(manifest["items"], start=1):
        estimate = item.get("price") or 0
        is_reward = item["type"] == "reward"
        product, created = Product.objects.get_or_create(
            title=item["title"],
            defaults={
                "kind": "reward" if is_reward else "merch",
                "category": item["category"],
                "description": (
                    "Награда колледжа. Выдаётся администратором."
                    if is_reward else
                    "Концептуальный макет 01:17. Цена указана ориентировочно; остаток и квоту настраивает администратор."
                ),
                "price": estimate,
                "asset_path": item.get("image", ""),
                "status": "off" if is_reward else "draft",
                "per_user_limit": None,
                "order": order,
            },
        )
        if not created:
            fields = []
            if not product.asset_path and item.get("image"):
                product.asset_path = item["image"]
                fields.append("asset_path")
            if product.price == 0 and estimate:
                product.price = estimate
                fields.append("price")
            if fields:
                product.save(update_fields=fields)
        if item.get("track") and item["track"] in tracks:
            product.tracks.add(tracks[item["track"]])
        ProductVariant.objects.get_or_create(product=product, name="—", defaults={"stock": 0})


class Migration(migrations.Migration):
    dependencies = [("shop", "0006_seed_merch_catalog")]

    operations = [migrations.RunPython(set_estimate_prices_and_extras, migrations.RunPython.noop)]
