from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "BiasHawk"

    def ready(self):
        # Registers the post_delete handlers that clean up MEDIA_ROOT.
        from core import signals  # noqa: F401
