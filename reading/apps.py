from django.apps import AppConfig


class ReadingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reading'
    verbose_name = 'Чтение и цели'

    def ready(self):
        from . import receivers  # noqa: F401  (подключение обработчиков сигналов)
