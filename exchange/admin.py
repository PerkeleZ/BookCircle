from django.contrib import admin

from .models import Copy, Loan

admin.site.register(Copy)


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('copy', 'borrower', 'status', 'requested_return_date')
    list_filter = ('status',)
