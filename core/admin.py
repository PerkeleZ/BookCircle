from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Book, BookEdit, Copy, Loan, Meeting, MeetingParticipant, ReadingEntry, ReadingGoal, Review, User


@admin.register(User)
class BookCircleUserAdmin(UserAdmin):  # роли назначаются здесь — только администратором
    fieldsets = UserAdmin.fieldsets + (('BookCircle', {'fields': ('role', 'bio')}),)
    list_display = ('username', 'email', 'role', 'is_staff')
    list_filter = UserAdmin.list_filter + ('role',)


for m in (Book, BookEdit, Copy, Loan, ReadingEntry, Review, Meeting, MeetingParticipant, ReadingGoal):
    admin.site.register(m)
