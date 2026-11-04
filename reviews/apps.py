from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reviews'
    verbose_name = 'Рецензии'

    def ready(self):
        from . import receivers  # noqa: F401  (подключение обработчиков сигналов)
