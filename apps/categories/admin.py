from django.contrib import admin

from .models import Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "user", "is_archived", "created_at")
    list_filter = ("kind", "is_archived")
    search_fields = ("name", "user__email")
    readonly_fields = ("created_at", "updated_at")
