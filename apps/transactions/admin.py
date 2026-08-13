from django.contrib import admin

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Read-only: mutating through admin would bypass apps.transactions.services
    and silently desync Account.balance from the ledger. A mutation-safe admin
    path (with the audit trail the spec requires) is Milestone 7's job.
    """

    list_display = (
        "date",
        "type",
        "user",
        "account",
        "transfer_to_account",
        "category",
        "amount",
    )
    list_filter = ("type", "currency")
    search_fields = ("user__email", "account__name", "note")
    date_hierarchy = "date"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
