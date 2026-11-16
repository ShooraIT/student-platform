import json
from pathlib import Path

from django.conf import settings
from django.db import migrations


def sync_catalog(apps, schema_editor):
    Product = apps.get_model("shop", "Product")
    ProductVariant = apps.get_model("shop", "ProductVariant")
    Track = apps.get_model("career", "Track")
    path = Path(settings.BASE_DIR) / "static" / "shop" / "merch" / "catalog.json"
    with path.open(encoding="utf-8") as source:
        manifest = json.load(source)
    tracks = {track.slug: track for track in Track.objects.all()}

    Product.objects.filter(asset_path__in=[
        "shop/merch/base-puller.webp", "shop/merch/base-stickers.webp", "shop/merch/sticker-3d.svg",
    ]).update(status="off")

    for order, item in enumerate(manifest["items"], start=1):
        if item.get("type") == "reward":
            continue
        product, created = Product.objects.get_or_create(
            title=item["title"],
            defaults={
                "kind": "merch", "category": item["category"],
                "description": item.get("label") or "Мерч коллекции 01:17.",
                "price": item.get("price") or 0, "asset_path": item.get("image", ""),
                "status": "draft", "per_user_limit": None, "order": order,
            },
        )
        if not created:
            product.category = item["category"]
            product.description = item.get("label") or "Мерч коллекции 01:17."
            product.price = item.get("price") or 0
            product.asset_path = item.get("image", "")
            product.order = order
            product.save(update_fields=["category", "description", "price", "asset_path", "order"])
        if item.get("track") in tracks:
            product.tracks.set([tracks[item["track"]]])
        else:
            product.tracks.clear()
        ProductVariant.objects.get_or_create(product=product, name="—", defaults={"stock": 0})


class Migration(migrations.Migration):
    dependencies = [("shop", "0008_add_special_finish_stickers"), ("career", "0011_sync_verified_partners")]
    operations = [migrations.RunPython(sync_catalog, migrations.RunPython.noop)]