FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=config.settings.prod
WORKDIR /app
RUN useradd --create-home --uid 10001 app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app . .
# статика собирается при сборке образа (хэши в именах файлов → вечный кэш в браузере и CDN)
RUN SECRET_KEY=build-only python manage.py collectstatic --noinput && chown -R app:app staticfiles
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=25s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"
# веб-процесс; воркер и планировщик запускаются из этого же образа другой командой (см. docker-compose.yml)
CMD ["gunicorn", "config.wsgi:application", "--config", "deploy/gunicorn.conf.py"]
