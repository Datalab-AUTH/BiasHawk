"""
Django settings for the BiasHawk backend.

Configuration comes from the environment. There are two ways it gets there:

  * local dev  , `.env` at the repo root, loaded below by python-dotenv
  * docker     , `docker.env`, injected by compose as real environment variables

Real environment variables always win: `load_dotenv` does not override them, and
`.env` is excluded from the image by .dockerignore, so a container never reads it.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# backend/config/settings.py -> backend/ -> repo root
BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent

load_dotenv(REPO_ROOT / ".env")


# --------------------------------------------------------------------------
# env helpers
# --------------------------------------------------------------------------

class ImproperlyConfigured(Exception):
    pass


def env(key, default=None, *, required=False):
    value = os.environ.get(key, default)
    if required and not value:
        raise ImproperlyConfigured(f"{key} is not set. Add it to .env or docker.env.")
    return value


def env_bool(key, default=False):
    return os.environ.get(key, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_int(key, default):
    raw = os.environ.get(key)
    if raw is None or not raw.strip():
        return default
    return int(raw.strip())


def env_list(key, default=""):
    """Comma-separated env value -> list of stripped, non-empty strings."""
    return [item.strip() for item in os.environ.get(key, default).split(",") if item.strip()]


# --------------------------------------------------------------------------
# core
# --------------------------------------------------------------------------

DEBUG = env_bool("DEBUG", False)

SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="dev-only-insecure-key-do-not-use-in-production" if DEBUG else None,
    required=not DEBUG,
)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")

# The frontend origin(s). Drives CORS and CSRF trust, so it must be the full
# scheme://host[:port] , "http://localhost:3000", not "localhost:3000".
FRONTEND_URLS = env_list("FRONTEND_URLS", "http://localhost:3000")

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# API paths are written without trailing slashes; don't let Django redirect them.
APPEND_SLASH = False


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",  # required for the pgvector HNSW index
    "django.contrib.sites",  # required by allauth
    "corsheaders",
    "rest_framework",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.github",
    "allauth.headless",
    "core",
]

SITE_ID = 1

MIDDLEWARE = [
    # CorsMiddleware must precede CommonMiddleware so preflights short-circuit.
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Must come after AuthenticationMiddleware.
    "allauth.account.middleware.AccountMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# --------------------------------------------------------------------------
# database , one Postgres, pgvector enabled by core migration 0001
# --------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", required=True),
        "USER": env("DB_USER", required=True),
        "PASSWORD": env("DB_PASSWORD", required=True),
        "HOST": env("DB_HOST", "127.0.0.1"),
        "PORT": env("DB_PORT", "5432"),
        # Job runner threads each hold a connection; recycle rather than pool.
        "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
        "CONN_HEALTH_CHECKS": True,
    }
}


# --------------------------------------------------------------------------
# auth , session cookies, not bearer tokens
#
# The frontend and the API are same-site (biashawk.example / api.biashawk.example,
# and localhost:3000 / localhost:8000 in dev), so a SameSite=Lax session cookie
# reaches both. That removes JWT signing and the /api/token round trip entirely.
# --------------------------------------------------------------------------

AUTH_USER_MODEL = "core.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# --- allauth: email/password, Google and GitHub, all against this database ---

ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_UNIQUE_EMAIL = True
# Our User has no username column. allauth defaults this to "username" and will
# raise KeyError on the missing field during signup unless it is set to None.
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_USER_MODEL_EMAIL_FIELD = "email"
ACCOUNT_PREVENT_ENUMERATION = True
ACCOUNT_ADAPTER = "core.auth.AccountAdapter"
SOCIALACCOUNT_ADAPTER = "core.auth.SocialAccountAdapter"

# The old frontend created users with emailVerified=null and then refused to log
# them in, with no email sender anywhere in the repo , accounts could only be
# activated by hand in the database. Verification stays off until an SMTP
# provider is actually configured; flip this env var when one is.
ACCOUNT_EMAIL_VERIFICATION = env("ACCOUNT_EMAIL_VERIFICATION", "none")

# Trust the email a provider asserts, so Google/GitHub sign-in doesn't bounce
# through a verification step that cannot currently be delivered.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

_FRONTEND = FRONTEND_URLS[0] if FRONTEND_URLS else "http://localhost:3000"

HEADLESS_ONLY = True
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": f"{_FRONTEND}/verify-email/{{key}}",
    "account_reset_password": f"{_FRONTEND}/password/reset",
    "account_reset_password_from_key": f"{_FRONTEND}/password/reset/{{key}}",
    "account_signup": f"{_FRONTEND}/sign-up",
    "socialaccount_login_error": f"{_FRONTEND}/sign-in?error=oauth",
}


def _social_app(client_id, secret):
    """Register a provider only when its credentials are actually present."""
    if not client_id or not secret:
        return []
    return [{"client_id": client_id, "secret": secret, "key": ""}]


SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": _social_app(env("GOOGLE_CLIENT_ID"), env("GOOGLE_CLIENT_SECRET")),
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
    "github": {
        "APPS": _social_app(env("GITHUB_CLIENT_ID"), env("GITHUB_CLIENT_SECRET")),
        "SCOPE": ["read:user", "user:email"],
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE", 60 * 60 * 24 * 7)  # 7 days
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
# The frontend must read this to echo it back as X-CSRFToken.
CSRF_COOKIE_HTTPONLY = False

# Cookie domain shared across the app and API subdomains, e.g. ".biashawk.example".
# Unset in dev, where both sides are on localhost.
SESSION_COOKIE_DOMAIN = env("COOKIE_DOMAIN") or None
CSRF_COOKIE_DOMAIN = SESSION_COOKIE_DOMAIN

CSRF_TRUSTED_ORIGINS = FRONTEND_URLS


# --------------------------------------------------------------------------
# CORS
# --------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = FRONTEND_URLS
CORS_ALLOW_CREDENTIALS = True  # required for the session cookie to be sent
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]


# --------------------------------------------------------------------------
# DRF , locked down by default; endpoints opt out explicitly
# --------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

if DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] += (
        "rest_framework.renderers.BrowsableAPIRenderer",
    )


# --------------------------------------------------------------------------
# production hardening
# --------------------------------------------------------------------------

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 60 * 60 * 24 * 30)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # Behind nginx: trust its scheme header so request.is_secure() is correct.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True


# --------------------------------------------------------------------------
# static and media
#
# Media is served by an ownership-checked view, never straight off disk ,
# /media/usecases/<uuid>/... was a public URL in the old stack.
# --------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}


# --------------------------------------------------------------------------
# job runner
# --------------------------------------------------------------------------

JOB_THREADS = env_int("JOB_THREADS", 8)
JOB_POLL_SECONDS = env_int("JOB_POLL_SECONDS", 2)
JOB_MAX_ATTEMPTS = env_int("JOB_MAX_ATTEMPTS", 3)
# A job whose lock is older than this is assumed dead and returned to the queue.
JOB_STALE_SECONDS = env_int("JOB_STALE_SECONDS", 60 * 30)


# --------------------------------------------------------------------------
# LLM , Open WebUI only. There is no OpenAI code path.
# --------------------------------------------------------------------------

OPENWEBUI_BASE_URL = env("OPENWEBUI_BASE_URL", "").rstrip("/")
OPENWEBUI_API_KEY = env("OPENWEBUI_API_KEY", "")
OPENWEBUI_CHAT_MODEL = env("OPENWEBUI_CHAT_MODEL", "datalab-1:latest")
OPENWEBUI_TIMEOUT = env_int("OPENWEBUI_TIMEOUT", 180)

# Embeddings run on Open WebUI too, on the server's GPU. Reranking stays
# in-process , Open WebUI exposes no reranking endpoint.
OPENWEBUI_EMBED_MODEL = env("OPENWEBUI_EMBED_MODEL", "nomic-embed-text:v1.5")
RERANKER_MODEL = env("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
CHUNK_SIZE = env_int("CHUNK_SIZE", 1000)
CHUNK_OVERLAP = env_int("CHUNK_OVERLAP", 200)

# The width of DocumentChunk.embedding, fixed at migration time. Changing the
# embedding model changes this, which invalidates every stored chunk , see
# `manage.py check_embeddings`, which fails loudly rather than letting inserts
# break on a dimension mismatch.
EMBEDDING_DIM = env_int("EMBEDDING_DIM", 768)

# Retrieval: fetch wide by vector distance, then let the cross-encoder pick.
#
# The old service retrieved 10 and reranked to 3, which is self-defeating , a
# relevant chunk sitting at vector rank 13 never reaches the reranker that would
# have scored it +4.4 against -3.3 for everything else. Vector distance is for
# recall; the reranker is for precision.
RAG_TOP_K = env_int("RAG_TOP_K", 30)
RAG_TOP_N_RERANK = env_int("RAG_TOP_N_RERANK", 3)
# HyDE: embed a hypothetical answer rather than the question itself.
#
# Off by default, which is also what the old service defaulted to ("basic").
# HyDE helps on broad thematic questions but actively hurts factual lookup: for
# "which organisation provides this system" the model confidently invents a name
# and embedding that fabrication pulls retrieval toward the wrong document. Every
# question the extraction agents ask is of exactly that factual kind.
RAG_USE_HYDE = env_bool("RAG_USE_HYDE", False)


# --------------------------------------------------------------------------
# i18n, email, logging
# --------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", "Europe/Athens")
USE_I18N = True
USE_TZ = True

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "{asctime} {levelname:<7} {name} , {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.db.backends": {"level": "INFO"},
        "core": {"level": env("LOG_LEVEL", "INFO"), "propagate": True},
    },
}
