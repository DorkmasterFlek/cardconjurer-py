from django.apps import AppConfig


class CreatorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'creator'

    def ready(self):
        # Implicitly connect signal handlers decorated with @receiver.
        from . import signals
