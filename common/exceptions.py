from rest_framework.exceptions import APIException


class Conflict(APIException):  # 409 — конфликт состояния
    status_code = 409
    default_detail = 'Конфликт состояния.'
    default_code = 'conflict'


class Bad(APIException):  # 400 с понятным сообщением
    status_code = 400
    default_code = 'bad_request'


class Unavailable(APIException):  # 503
    status_code = 503
    default_detail = 'Сервис временно недоступен.'
    default_code = 'unavailable'
