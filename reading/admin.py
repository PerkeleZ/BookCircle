from django.contrib import admin

from .models import ReadingEntry, ReadingGoal

admin.site.register(ReadingEntry)
admin.site.register(ReadingGoal)
