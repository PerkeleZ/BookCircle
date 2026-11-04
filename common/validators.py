import re

from rest_framework import serializers


def validate_phone_number(v):
    v = (v or '').strip()
    digits = re.sub(r'\D', '', v)
    if not re.match(r'^\+?[\d\s\-()]{9,20}$', v) or not 9 <= len(digits) <= 15:
        raise serializers.ValidationError('Укажите номер телефона, например +996 555 123 456.')
    return v
