from django.contrib import admin

from .models import BudgetDefinition, BudgetPeriod


class ReadOnlyAdminMixin:
    """Mutating through admin would bypass apps.budgets.services and either
    skip BudgetDefinition.clean() or silently desync a BudgetPeriod's frozen
    amount from history. A mutation-safe, audit-logged admin path is
    Milestone 7's job — same rationale as TransactionAdmin.
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BudgetDefinition)
class BudgetDefinitionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("user", "category", "scope", "amount", "is_archived")
    list_filter = ("scope", "is_archived")
    search_fields = ("user__email", "category__name")


@admin.register(BudgetPeriod)
class BudgetPeriodAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("definition", "period_start", "period_end", "amount")
    list_filter = ("period_start",)
    search_fields = ("user__email", "definition__category__name")
    date_hierarchy = "period_start"
