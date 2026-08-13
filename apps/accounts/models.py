from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimeStampedModel


class AccountType(models.TextChoices):
    CASH = "CASH", "Cash"
    BANK = "BANK", "Bank"
    E_WALLET = "E_WALLET", "E-Wallet"
    CREDIT_CARD = "CREDIT_CARD", "Credit Card"
    OTHER = "OTHER", "Other"


class AccountQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_archived=False)

    def archived(self):
        return self.filter(is_archived=True)


class Account(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="accounts"
    )
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=AccountType.choices)
    currency = models.CharField(max_length=3)
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)

    objects = AccountQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                condition=Q(is_archived=False),
                name="unique_active_account_name_per_user",
            )
        ]
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.user_id and self.currency and self.currency != self.user.profile.base_currency:
            raise ValidationError(
                {"currency": "Account currency must match your profile's base currency."}
            )

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.balance = self.opening_balance
        super().save(*args, **kwargs)

    def archive(self):
        self.is_archived = True
        self.archived_at = timezone.now()
        self.save(update_fields=["is_archived", "archived_at", "updated_at"])

    def adjust_balance(self, delta):
        """Row-locked balance mutation — the primitive Milestone 4's transaction
        writes will call inside their own atomic block. Safe to call standalone too.
        """
        with transaction.atomic():
            locked = Account.objects.select_for_update().get(pk=self.pk)
            locked.balance += delta
            locked.save(update_fields=["balance", "updated_at"])
            self.balance = locked.balance

    def set_opening_balance(self, new_opening_balance):
        """Corrects the ledger's baseline, not an event in it — shifts the
        current balance by the same delta so every transaction's recorded
        effect is left untouched, and reconcile_balances stays consistent
        without a matching Transaction row.
        """
        with transaction.atomic():
            locked = Account.objects.select_for_update().get(pk=self.pk)
            delta = new_opening_balance - locked.opening_balance
            locked.opening_balance = new_opening_balance
            locked.balance += delta
            locked.save(update_fields=["opening_balance", "balance", "updated_at"])
            self.opening_balance = locked.opening_balance
            self.balance = locked.balance
