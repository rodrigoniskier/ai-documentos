import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret")
DEBUG = env_bool("DEBUG", True)
if not DEBUG and SECRET_KEY == "dev-secret":
    raise RuntimeError("DJANGO_SECRET_KEY é obrigatória em produção.")

ALLOWED_HOSTS = [
    item.strip()
    for item in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if item.strip()
]
CSRF_TRUSTED_ORIGINS = [
    item.strip()
    for item in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if item.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "storages",
    "platform_app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "platform_app.middleware.BillingExpiryMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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
                "platform_app.context.platform",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"

DATABASE_URL = os.getenv("DATABASE_URL", "")
DATABASES = {
    "default": dj_database_url.config(
        default=DATABASE_URL or f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Fortaleza"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
}

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "")
AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL", "")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "auto")
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = env_bool("AWS_QUERYSTRING_AUTH", True)
AWS_QUERYSTRING_EXPIRE = int(os.getenv("AWS_QUERYSTRING_EXPIRE", "600"))
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_S3_ADDRESSING_STYLE = "path"
AWS_S3_FILE_OVERWRITE = False

if AWS_STORAGE_BUCKET_NAME:
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "platform_app.User"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "home"

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "backuprodrigoniskier@gmail.com")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", SUPPORT_EMAIL)
TERMS_VERSION = os.getenv("TERMS_VERSION", "2026-07-28")
PRIVACY_VERSION = os.getenv("PRIVACY_VERSION", "2026-07-28")

ASAAS_ENABLED = env_bool("ASAAS_ENABLED", False)
ASAAS_API_KEY = os.getenv("ASAAS_API_KEY", "")
ASAAS_BASE_URL = os.getenv("ASAAS_BASE_URL", "https://api.asaas.com/v3").rstrip("/")
ASAAS_WEBHOOK_TOKEN = os.getenv("ASAAS_WEBHOOK_TOKEN", "")
ASAAS_CHECKOUT_EXPIRATION_MINUTES = int(
    os.getenv("ASAAS_CHECKOUT_EXPIRATION_MINUTES", "60")
)
ASAAS_HTTP_TIMEOUT = int(os.getenv("ASAAS_HTTP_TIMEOUT", "60"))
ASAAS_BILLING_TYPES = os.getenv("ASAAS_BILLING_TYPES", "CREDIT_CARD")
ASAAS_WEBHOOK_NAME = os.getenv(
    "ASAAS_WEBHOOK_NAME", "AjudAI Docente — Asaas Produção"
)
ASAAS_WEBHOOK_EMAIL = os.getenv("ASAAS_WEBHOOK_EMAIL", SUPPORT_EMAIL)

if ASAAS_ENABLED:
    if not ASAAS_API_KEY:
        raise RuntimeError("ASAAS_API_KEY é obrigatória quando ASAAS_ENABLED=true.")
    if len(ASAAS_WEBHOOK_TOKEN) < 32:
        raise RuntimeError(
            "ASAAS_WEBHOOK_TOKEN deve possuir pelo menos 32 caracteres quando "
            "ASAAS_ENABLED=true."
        )
    if not 10 <= ASAAS_CHECKOUT_EXPIRATION_MINUTES <= 1440:
        raise RuntimeError(
            "ASAAS_CHECKOUT_EXPIRATION_MINUTES deve estar entre 10 e 1440."
        )
    if ASAAS_HTTP_TIMEOUT < 10:
        raise RuntimeError("ASAAS_HTTP_TIMEOUT deve ser de pelo menos 10 segundos.")
    if not PUBLIC_BASE_URL and not DEBUG:
        raise RuntimeError(
            "PUBLIC_BASE_URL é obrigatória em produção quando ASAAS_ENABLED=true."
        )

if not DEBUG:
    missing = []
    for name, value in {
        "DATABASE_URL": DATABASE_URL,
        "PUBLIC_BASE_URL": PUBLIC_BASE_URL,
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "AWS_ACCESS_KEY_ID": AWS_ACCESS_KEY_ID,
        "AWS_SECRET_ACCESS_KEY": AWS_SECRET_ACCESS_KEY,
        "AWS_STORAGE_BUCKET_NAME": AWS_STORAGE_BUCKET_NAME,
        "AWS_S3_ENDPOINT_URL": AWS_S3_ENDPOINT_URL,
    }.items():
        if not value:
            missing.append(name)
    if missing:
        raise RuntimeError(
            "Variáveis obrigatórias ausentes em produção: " + ", ".join(missing)
        )

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_SAMESITE = "Lax"
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    X_FRAME_OPTIONS = "DENY"

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
