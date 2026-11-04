from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from common.validators import validate_phone_number

from .models import User


class UserSerializer(serializers.ModelSerializer):
    has_password = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'bio', 'phone', 'notify_email', 'role', 'google_email', 'has_password']
        read_only_fields = ['id', 'username', 'role', 'google_email']  # роль назначает только администратор

    def get_has_password(self, o):
        return o.has_usable_password()

    def validate_email(self, v):
        if v and User.objects.filter(email__iexact=v).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError('Пользователь с таким email уже зарегистрирован.')
        return v

    def validate_phone(self, v):
        return validate_phone_number(v) if v.strip() else ''


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        extra_kwargs = {'email': {'required': True, 'allow_blank': False}}

    def validate_email(self, v):
        if User.objects.filter(email__iexact=v).exists():
            raise serializers.ValidationError('Пользователь с таким email уже зарегистрирован.')
        return v

    def validate_password(self, v):
        validate_password(v)
        return v

    def create(self, d):
        return User.objects.create_user(**d)
