"""Генерация VAPID-ключей для Web Push (без зависимостей от Django — используется и в settings)."""
import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def generate():
    key = ec.generate_private_key(ec.SECP256R1())
    private = _b64(key.private_numbers().private_value.to_bytes(32, "big"))
    public = _b64(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
    return {"public": public, "private": private}


def load_or_create(path: Path):
    """Для локальной разработки: ключи в файле .vapid.json (в .gitignore)."""
    if path.exists():
        return json.loads(path.read_text())
    keys = generate()
    path.write_text(json.dumps(keys))
    return keys
