from django.conf import settings


class NotConfigured(Exception):
    pass


class InvalidCredential(Exception):
    pass


def verify(credential):
    """Проверяет Google ID-токен (подпись, срок, audience, issuer) и возвращает его данные."""
    if not settings.GOOGLE_CLIENT_ID:
        raise NotConfigured()
    from google.auth.transport import requests as g_requests
    from google.oauth2 import id_token
    try:
        info = id_token.verify_oauth2_token(credential, g_requests.Request(), settings.GOOGLE_CLIENT_ID)
    except ValueError:
        raise InvalidCredential()
    if not info.get('sub') or not info.get('email') or not info.get('email_verified'):
        raise InvalidCredential()
    return info
