from django.contrib import admin

from .models import Account


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "user", "currency", "balance", "is_archived")
    list_filter = ("type", "currency", "is_archived")
    search_fields = ("name", "user__email")
    readonly_fields = ("balance", "created_at", "updated_at")
