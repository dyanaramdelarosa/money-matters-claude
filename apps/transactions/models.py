from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.accounts.models import Account
from apps.categories.models import Category
from apps.core.models import TimeStampedModel


class TransactionType(models.TextChoices):
    EXPENSE = "EXPENSE", "Expense"
    INCOME = "INCOME", "Income"
    TRANSFER = "TRANSFER", "Transfer"
    ADJUSTMENT = "ADJUSTMENT", "Balance Correction"


class Transaction(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions"
    )
    type = models.CharField(max_length=20, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3)
    date = models.DateField(default=timezone.localdate)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="transactions")
    transfer_to_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="incoming_transfers",
        null=True,
        blank=True,
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="transactions",
        null=True,
        blank=True,
    )
    note = models.TextField(blank=True, default="")
    receipt_reference = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [models.Index(fields=["user", "date"])]

    def __str__(self):
        return f"{self.get_type_display()} {self.amount} ({self.date})"

    def clean(self):
        if self.account_id and self.user_id and self.account.user_id != self.user_id:
            raise ValidationError({"account": "Account must belong to you."})
        if self.account_id and self.currency and self.currency != self.account.currency:
            raise ValidationError(
                {"currency": "Transaction currency must match the account's currency."}
            )

        if self.type == TransactionType.TRANSFER:
            if not self.transfer_to_account_id:
                raise ValidationError(
                    {"transfer_to_account": "A destination account is required for transfers."}
                )
            if self.transfer_to_account_id == self.account_id:
                raise ValidationError(
                    {"transfer_to_account": "Cannot transfer to the same account."}
                )
            if self.user_id and self.transfer_to_account.user_id != self.user_id:
                raise ValidationError({"transfer_to_account": "Account must belong to you."})
            if self.currency and self.currency != self.transfer_to_account.currency:
                raise ValidationError(
                    {
                        "transfer_to_account": "Transaction currency must match the "
                        "destination account's currency."
                    }
                )
            if self.category_id:
                raise ValidationError({"category": "Transfers cannot have a category."})
            if self.amount is not None and self.amount <= 0:
                raise ValidationError({"amount": "Amount must be greater than zero."})
        elif self.type == TransactionType.ADJUSTMENT:
            if self.transfer_to_account_id:
                raise ValidationError(
                    {"transfer_to_account": "Only transfers use a destination account."}
                )
            if self.category_id:
                raise ValidationError({"category": "Balance corrections cannot have a category."})
            if self.amount == 0:
                raise ValidationError({"amount": "Correction amount cannot be zero."})
        else:
            if self.transfer_to_account_id:
                raise ValidationError(
                    {"transfer_to_account": "Only transfers use a destination account."}
                )
            if not self.category_id:
                raise ValidationError({"category": "Category is required."})
            elif self.category.kind != self.type:
                raise ValidationError(
                    {"category": f"Category must be an {self.get_type_display()} category."}
                )
            if self.amount is not None and self.amount <= 0:
                raise ValidationError({"amount": "Amount must be greater than zero."})

    def _effects(self):
        """The signed balance delta(s) this transaction's current field values
        represent, as [(account, delta), ...]. Reused by both the service layer
        (apply on create, reverse+reapply on edit, reverse on delete) and
        reconcile_balances (recompute from scratch).
        """
        if self.type in (TransactionType.INCOME, TransactionType.ADJUSTMENT):
            return [(self.account, self.amount)]
        if self.type == TransactionType.EXPENSE:
            return [(self.account, -self.amount)]
        return [(self.account, -self.amount), (self.transfer_to_account, self.amount)]
