import logging
import time
import uuid

logger = logging.getLogger('bookcircle.request')


class RequestLogMiddleware:
    """Сквозной X-Request-ID и строка лога с временем ответа для каждого запроса."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.headers.get('X-Request-ID') or uuid.uuid4().hex[:12]
        request.request_id = rid
        start = time.perf_counter()
        response = self.get_response(request)
        ms = round((time.perf_counter() - start) * 1000)
        response['X-Request-ID'] = rid
        if not request.path.startswith(('/static/', '/healthz', '/readyz')):
            user = getattr(request, 'user', None)
            logger.info('%s %s -> %s (%d ms)', request.method, request.path, response.status_code, ms, extra={
                'request_id': rid, 'method': request.method, 'path': request.path, 'status': response.status_code,
                'ms': ms, 'user_id': user.id if user is not None and user.is_authenticated else None})
        return response
