from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse


def healthz(request):
    """Liveness: процесс жив (для оркестратора). Зависимости не проверяет."""
    return JsonResponse({'status': 'ok'})


def readyz(request):
    """Readiness: можно ли отправлять трафик на этот экземпляр (БД и кэш отвечают)."""
    checks = {}
    try:
        connection.ensure_connection()
        checks['database'] = 'ok'
    except Exception as e:  # noqa: BLE001
        checks['database'] = f'error: {type(e).__name__}'
    try:
        cache.set('readyz', '1', 5)
        checks['cache'] = 'ok' if cache.get('readyz') == '1' else 'error: not stored'
    except Exception as e:  # noqa: BLE001
        checks['cache'] = f'error: {type(e).__name__}'
    ok = all(v == 'ok' for v in checks.values())
    return JsonResponse({'status': 'ok' if ok else 'unavailable', 'checks': checks}, status=200 if ok else 503)
