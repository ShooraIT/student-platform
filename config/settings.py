"""Настройки платформы «01:17». Секреты и параметры окружения — через переменные окружения."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return str(env(name, str(default))).lower() in ("1", "true", "yes", "on")


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
CSRF_TRUSTED_ORIGINS = [o for o in env("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "core",
    "accounts",
    "wallet",
    "events",
    "assignments",
    "surveys",
    "shop",
    "draws",
    "achievements",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.ForcePasswordChangeMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.platform",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

if env("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB"),
            "USER": env("POSTGRES_USER", "postgres"),
            "PASSWORD": env("POSTGRES_PASSWORD", ""),
            "HOST": env("POSTGRES_HOST", "localhost"),
            "PORT": env("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "accounts:login"

LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31536000

# --- Вход через МЭШ (СУДИР mos.ru, OAuth 2.0 / OIDC) ---
# Адреса и ключи выдаются при подключении к СУДИР. Пока MESH_CLIENT_ID пуст, кнопка входа через МЭШ скрыта.
MESH_OAUTH = {
    "CLIENT_ID": env("MESH_CLIENT_ID", ""),
    "CLIENT_SECRET": env("MESH_CLIENT_SECRET", ""),
    "AUTHORIZE_URL": env("MESH_AUTHORIZE_URL", ""),
    "TOKEN_URL": env("MESH_TOKEN_URL", ""),
    "USERINFO_URL": env("MESH_USERINFO_URL", ""),
    "SCOPE": env("MESH_SCOPE", "openid profile email"),
    # Соответствие полей ответа userinfo полям платформы
    "FIELD_ID": env("MESH_FIELD_ID", "sub"),
    "FIELD_LAST_NAME": env("MESH_FIELD_LAST_NAME", "LastName"),
    "FIELD_FIRST_NAME": env("MESH_FIELD_FIRST_NAME", "FirstName"),
    "FIELD_MIDDLE_NAME": env("MESH_FIELD_MIDDLE_NAME", "MiddleName"),
    "FIELD_EMAIL": env("MESH_FIELD_EMAIL", "mail"),
    "FIELD_BIRTH_DATE": env("MESH_FIELD_BIRTH_DATE", "birthdate"),
}

# Резервный вход по логину и паролю для студентов (п. 3.2 ТЗ)
STUDENT_PASSWORD_LOGIN = env_bool("STUDENT_PASSWORD_LOGIN", True)

# Чек-ин по QR: период смены кода (секунды)
QR_ROTATION_SECONDS = int(env("QR_ROTATION_SECONDS", "30"))

# Версионирование статики в продакшене (сброс кэша браузера после обновлений)
if not DEBUG:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
    }

# --- Web Push (п. 11 ТЗ) ---
# В продакшене ключи задаются переменными (сгенерировать: python manage.py generate_vapid).
# Локально, если переменных нет, ключи создаются в файле .vapid.json.
VAPID_PUBLIC_KEY = env("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = env("VAPID_PRIVATE_KEY", "")
if DEBUG and not VAPID_PUBLIC_KEY:
    from notifications.vapid import load_or_create as _vapid_keys

    _keys = _vapid_keys(BASE_DIR / ".vapid.json")
    VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY = _keys["public"], _keys["private"]
VAPID_SUBJECT = env("VAPID_SUBJECT", "mailto:admin@example.ru")
PUSH_TITLE = env("PUSH_TITLE", "01:17")
# Отправлять пуш сразу при создании уведомления (удобно локально). В продакшене пуши шлёт сервис scheduler.
PUSH_SEND_INLINE = env_bool("PUSH_SEND_INLINE", DEBUG)

# Уровни: сколько заработанных степов нужно на один уровень
LEVEL_STEPS = int(env("LEVEL_STEPS", "200"))
