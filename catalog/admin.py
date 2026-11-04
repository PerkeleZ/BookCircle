from django.contrib import admin

from .models import Book, BookEdit


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'genre', 'status')
    list_filter = ('status', 'genre')
    search_fields = ('title', 'author')


admin.site.register(BookEdit)
