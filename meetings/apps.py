from django.apps import AppConfig


class MeetingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'meetings'
    verbose_name = 'Книжные встречи'

    def ready(self):
        from . import receivers  # noqa: F401  (подключение обработчиков сигналов)
