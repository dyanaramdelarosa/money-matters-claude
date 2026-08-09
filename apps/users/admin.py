from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "base_currency", "created_at")
    list_filter = ("base_currency",)
    search_fields = ("user__email",)
    readonly_fields = ("created_at", "updated_at")
