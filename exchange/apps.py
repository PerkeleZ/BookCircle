from django.apps import AppConfig


class ExchangeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'exchange'
    verbose_name = 'Обмены книг'

    def ready(self):
        from . import receivers  # noqa: F401  (подключение обработчиков сигналов)
