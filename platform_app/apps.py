from django.apps import AppConfig


class PlatformAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "platform_app"

    def import_models(self):
        super().import_models()
        from . import document_models  # noqa: F401

    def ready(self):
        from . import signals  # noqa: F401
