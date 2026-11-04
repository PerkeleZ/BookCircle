import logging
import re
import secrets
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework import generics
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from common.exceptions import Bad, Conflict

from . import google_auth
from .models import PasswordResetCode, User
from .serializers import RegisterSerializer, UserSerializer


logger = logging.getLogger(__name__)


class MailFailed(APIException):
    status_code = 503
    default_detail = 'Не удалось отправить письмо. Проверьте настройку EMAIL_BACKEND в settings.py.'


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.save()
        return Response({'token': Token.objects.get_or_create(user=user)[0].key}, status=201)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        user = authenticate(username=request.data.get('username'), password=request.data.get('password'))
        if not user:
            raise Bad('Неверный логин или пароль.')
        return Response({'token': Token.objects.get_or_create(user=user)[0].key})


class LogoutView(APIView):
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=204)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


RESET_TTL = timedelta(minutes=10)


RESET_MAX_ATTEMPTS = 5


def _code_hash(user, code):  # в базе хранится только HMAC-хэш кода, не сам код
    return salted_hmac('bookcircle.pwreset', f'{user.pk}:{code}').hexdigest()


class PasswordResetRequest(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        email = (request.data.get('email') or '').strip()
        if not email:
            raise ValidationError({'email': ['Укажите email.']})
        users = list(User.objects.filter(email__iexact=email, is_active=True))
        if not users and (settings.DEBUG or settings.EMAIL_BACKEND.endswith('TerminalEmailBackend')):  # только в разработке: иначе непонятно, почему «ничего не пришло»
            print(f'\n[dev] Сброс пароля: пользователь с email «{email}» не найден — письмо не создано.\n', flush=True)
            raise NotFound(f'Аккаунт с email «{email}» не найден. (Подсказка режима разработки: '
                           f'в рабочей версии ответ одинаковый для любых адресов.)')
        for u in users:
            code = f'{secrets.randbelow(10 ** 6):06d}'
            PasswordResetCode.objects.filter(user=u).delete()  # новый код отменяет предыдущий
            PasswordResetCode.objects.create(user=u, code_hash=_code_hash(u, code))
            link = f"{settings.FRONTEND_URL}/#/reset?email={quote(u.email, safe='')}&code={code}"
            try:
                send_mail('BookCircle: код для сброса пароля',
                          f'Здравствуйте, {u.username}!\n\nВаш код для сброса пароля: {code}\n\n'
                          f'Или откройте ссылку — код подставится сам:\n{link}\n\n'
                          f'Код действует 10 минут и работает один раз. Если вы не запрашивали сброс — '
                          f'просто проигнорируйте это письмо.',
                          settings.DEFAULT_FROM_EMAIL, [u.email])
            except Exception:
                logger.exception('Не удалось отправить письмо сброса пароля')
                raise MailFailed()
        msg = 'Если аккаунт с таким email существует, код отправлен.'
        if settings.EMAIL_BACKEND.endswith('TerminalEmailBackend'):
            msg = 'Код выведен в терминал, где запущен сервер (почта и Gmail не используются).'
        return Response({'detail': msg})  # в рабочей версии ответ одинаков для любых email


class PasswordResetConfirm(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        email, code, pwd = (str(request.data.get(k) or '').strip() for k in ('email', 'code', 'password'))
        user = User.objects.filter(email__iexact=email, is_active=True).first() if email else None
        wrong = False
        with transaction.atomic():
            rc = PasswordResetCode.objects.select_for_update().filter(user=user).first() if user else None
            if not rc or timezone.now() - rc.created_at > RESET_TTL or rc.attempts >= RESET_MAX_ATTEMPTS:
                raise Bad('Код недействителен или устарел. Запросите новый.')
            if not constant_time_compare(rc.code_hash, _code_hash(user, code)):
                rc.attempts += 1
                rc.save(update_fields=['attempts'])
                wrong = True
        if wrong:  # исключение — вне транзакции, чтобы счётчик попыток сохранился
            raise ValidationError({'code': ['Неверный код.']})
        try:
            validate_password(pwd, user)
        except DjangoValidationError as e:
            raise ValidationError({'password': list(e.messages)})
        user.set_password(pwd)
        user.save()
        PasswordResetCode.objects.filter(user=user).delete()  # код одноразовый
        Token.objects.filter(user=user).delete()  # выход на всех устройствах
        return Response({'detail': 'Пароль изменён. Теперь можно войти.'})


class Unavailable(APIException):
    status_code = 503
    default_detail = 'Вход через Google не настроен на сервере (переменная GOOGLE_CLIENT_ID).'


def google_info(request):
    try:
        return google_auth.verify(request.data.get('credential') or '')
    except google_auth.NotConfigured:
        raise Unavailable()
    except google_auth.InvalidCredential:
        raise Bad('Не удалось проверить вход через Google. Попробуйте ещё раз.')


class PublicConfig(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({'client_id': settings.GOOGLE_CLIENT_ID})


class GoogleLogin(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        info = google_info(request)
        sub, email = info['sub'], info['email'].lower()
        user = User.objects.filter(google_sub=sub).first()
        if not user:
            # автопривязки по email нет: иначе можно угнать чужой аккаунт, зарегистрированный на чужой email
            if User.objects.filter(email__iexact=email).exists():
                raise Conflict('Аккаунт с этим email уже существует. Войдите по паролю и привяжите Google в профиле.')
            base = re.sub(r'[^\w.@+-]', '', email.split('@')[0])[:30] or 'user'
            name, n = base, 1
            while User.objects.filter(username=name).exists():
                n += 1
                name = f'{base}{n}'
            user = User(username=name, email=email, google_sub=sub, google_email=email)
            user.set_unusable_password()
            user.save()
        return Response({'token': Token.objects.get_or_create(user=user)[0].key})


class GoogleLink(APIView):
    def post(self, request):
        info = google_info(request)
        if User.objects.filter(google_sub=info['sub']).exclude(pk=request.user.pk).exists():
            raise Conflict('Этот Google-аккаунт уже привязан к другому пользователю.')
        request.user.google_sub = info['sub']
        request.user.google_email = info['email']
        request.user.save(update_fields=['google_sub', 'google_email'])
        return Response({'google_email': info['email']})


class GoogleUnlink(APIView):
    def post(self, request):
        if not request.user.has_usable_password():
            raise Conflict('Нельзя отвязать Google: у аккаунта нет пароля. Сначала задайте его через «Забыли пароль?».')
        request.user.google_sub = None
        request.user.google_email = ''
        request.user.save(update_fields=['google_sub', 'google_email'])
        return Response({'google_email': ''})
