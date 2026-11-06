"""Вход через МЭШ (СУДИР mos.ru) по OAuth 2.0 Authorization Code + PKCE (п. 3.1 ТЗ).

Конкретные адреса, scope и названия полей задаются в settings.MESH_OAUTH после подключения к СУДИР.
"""
import base64
import hashlib
import secrets
from datetime import datetime
from urllib.parse import urlencode

import requests
from django.conf import settings

from .models import UnmatchedMeshLogin, User


def enabled():
    c = settings.MESH_OAUTH
    return bool(c["CLIENT_ID"] and c["AUTHORIZE_URL"] and c["TOKEN_URL"] and c["USERINFO_URL"])


def authorize_url(request, redirect_uri):
    c = settings.MESH_OAUTH
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    request.session["mesh_state"] = state
    request.session["mesh_verifier"] = verifier
    params = {
        "response_type": "code",
        "client_id": c["CLIENT_ID"],
        "redirect_uri": redirect_uri,
        "scope": c["SCOPE"],
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return c["AUTHORIZE_URL"] + "?" + urlencode(params)


class MeshError(Exception):
    pass


def fetch_userinfo(request, code, state, redirect_uri):
    c = settings.MESH_OAUTH
    if not state or state != request.session.pop("mesh_state", None):
        raise MeshError("Сессия входа устарела, попробуйте ещё раз")
    verifier = request.session.pop("mesh_verifier", "")
    resp = requests.post(
        c["TOKEN_URL"],
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
        auth=(c["CLIENT_ID"], c["CLIENT_SECRET"]),
        timeout=15,
    )
    if resp.status_code != 200:
        raise MeshError("МЭШ не подтвердил вход")
    token = resp.json().get("access_token")
    info = requests.get(c["USERINFO_URL"], headers={"Authorization": f"Bearer {token}"}, timeout=15)
    if info.status_code != 200:
        raise MeshError("Не удалось получить данные пользователя из МЭШ")
    return info.json()  # токены не сохраняем


def _parse_birth(v):
    if not v:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(str(v)[:10], fmt).date()
        except ValueError:
            pass
    return None


def match_user(info):
    """Ищет студента по данным МЭШ. Возвращает User или None (тогда — очередь несопоставленных)."""
    c = settings.MESH_OAUTH
    mesh_id = str(info.get(c["FIELD_ID"], "")).strip()
    if not mesh_id:
        raise MeshError("МЭШ не передал идентификатор пользователя")
    user = User.objects.filter(mesh_id=mesh_id).first()
    if user:
        return user
    last = str(info.get(c["FIELD_LAST_NAME"], "")).strip()
    first = str(info.get(c["FIELD_FIRST_NAME"], "")).strip()
    middle = str(info.get(c["FIELD_MIDDLE_NAME"], "")).strip()
    email = str(info.get(c["FIELD_EMAIL"], "")).strip()
    birth = _parse_birth(info.get(c["FIELD_BIRTH_DATE"]))

    students = User.objects.filter(role=User.Role.STUDENT, expelled=False, mesh_id__isnull=True)
    found = None
    if email:
        found = students.filter(email__iexact=email).first()
    by_name = students.filter(last_name__iexact=last, first_name__iexact=first)
    if middle:
        by_name = by_name.filter(middle_name__iexact=middle)
    if not found and birth:
        found = by_name.filter(birth_date=birth).first()
    if not found and by_name.count() == 1:
        found = by_name.first()
    if found:
        found.mesh_id = mesh_id
        found.save(update_fields=["mesh_id"])
        return found

    um, _ = UnmatchedMeshLogin.objects.update_or_create(
        mesh_id=mesh_id,
        defaults=dict(last_name=last, first_name=first, middle_name=middle, email=email, birth_date=birth, raw=info),
    )
    um.candidates.set(by_name[:10])
    return None
