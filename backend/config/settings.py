"""
Django settings for the Inventory & Training Matrix standalone system.

Independent project — own .env, own SECRET_KEY, own database. See
../../docs (in the PDRRMO_v3 repo, docs/spec-inventory-system.md) for
the full build spec this project follows.
"""

import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# The built React SPA (frontend/dist/). Django + whitenoise serves it in
# production; the Vite dev server serves it in development.
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"

load_dotenv(BASE_DIR / ".env")


def _env_bool(name, default="False"):
    return os.getenv(name, default).strip().lower() in ("true", "1", "yes")


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError(
        "DJANGO_SECRET_KEY is not set. Copy .env.example to .env and fill "
        "it in before running the server."
    )

DEBUG = _env_bool("DJANGO_DEBUG", "True")

ALLOWED_HOSTS = [
    h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()
]

# CORS / CSRF for a split-origin frontend. The planned production deploy is
# single-origin (Django + whitenoise serves the built React bundle), so these
# are empty by default and act only as an env-gated fallback. In dev the Vite
# server proxies /api to Django, so no CORS is needed there either.
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    # apps.* modules are added here as the build order (spec Section 7)
    # reaches them.
    "apps.core",
]

# Auth paths, in order tried:
#  - JWT (Authorization: Bearer ...) — the React SPA (rebuild step R1+).
#  - Session (+ CSRF) — the Django admin and the plain-template/vanilla-JS
#    UI that stays live until the React rebuild's cutover (step R7).
#  - Basic — so endpoints can be curl-tested without a login/CSRF dance.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # frontend/dist so the SPA catch-all can render index.html.
        "DIRS": [FRONTEND_DIST],
        "APP_DIRS": True,  # still needed for the Django admin's templates
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.config(default=DATABASE_URL, conn_max_age=600),
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# The manifest storage above needs `collectstatic` to have run. For local dev
# (DEBUG), fall back to plain storage so admin static resolves with no build.
if DEBUG:
    STORAGES["staticfiles"]["BACKEND"] = (
        "django.contrib.staticfiles.storage.StaticFilesStorage"
    )

# whitenoise also serves the built SPA (index.html + /assets/*) straight from
# frontend/dist/; requests it can't satisfy fall through to the URLconf, where
# the SPA catch-all renders index.html for client-side routes.
WHITENOISE_ROOT = str(FRONTEND_DIST)
WHITENOISE_INDEX_FILE = True


def _immutable_spa_asset(path, url):
    """Everything Vite emits under /assets/ is content-hashed, so it is safe
    to cache forever. Whitenoise's default heuristic only recognises a dotted
    lowercase-hex hash and misses Vite's ``name-HASH.ext`` form; index.html
    lives at ``/`` and is never matched here (so it stays revalidated)."""
    return url.startswith("/assets/")


WHITENOISE_IMMUTABLE_FILE_TEST = _immutable_spa_asset

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Production hardening (spec Section 7, step 10)
# --------------------------------------------------------------------------
# All DEBUG-gated so local dev (SQLite, HTTP, Vite proxy) is unaffected.
# The deploy is single-origin (Django + whitenoise serves the built SPA),
# behind Render's TLS-terminating proxy.

if not DEBUG:
    # Render terminates TLS at its edge and forwards over HTTP with this
    # header, so Django can tell the original request was HTTPS. Render's
    # edge already forces HTTP->HTTPS for *.onrender.com, so an in-app
    # SECURE_SSL_REDIRECT is redundant here (and risks a health-check
    # redirect loop) — the proxy header + secure cookies are the useful part.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Render injects the service's own hostname at runtime. Fold it into
# ALLOWED_HOSTS + CSRF_TRUSTED_ORIGINS so the *.onrender.com subdomain need
# not be hardcoded before the service exists. The Django admin (session auth
# + CSRF, over HTTPS) needs its origin trusted for the login POST.
_RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
if _RENDER_HOST:
    if _RENDER_HOST not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_RENDER_HOST)
    _render_origin = f"https://{_RENDER_HOST}"
    if _render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_render_origin)
