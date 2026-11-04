from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import PasswordResetCode, User


@admin.register(User)
class BookCircleUserAdmin(UserAdmin):  # роли назначаются здесь — только администратором
    fieldsets = UserAdmin.fieldsets + (('BookCircle', {'fields': ('role', 'bio', 'phone', 'notify_email')}),)
    list_display = ('username', 'email', 'role', 'is_staff')
    list_filter = UserAdmin.list_filter + ('role',)


admin.site.register(PasswordResetCode)
