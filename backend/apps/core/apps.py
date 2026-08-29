from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = "Core / Reference Data"

    def ready(self):
        from . import signals  # noqa: F401  (registers the post_save receiver)
