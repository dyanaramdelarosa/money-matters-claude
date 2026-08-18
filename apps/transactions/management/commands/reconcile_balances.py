import sys
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.db.models import Sum

from apps.accounts.models import Account
from apps.transactions.models import Transaction, TransactionType
from apps.transactions.services import signed_amount_expression


class Command(BaseCommand):
    help = (
        "Recompute every account's balance from opening_balance plus the transaction "
        "ledger, report any drift from the stored (cached) balance, and optionally "
        "correct it with --fix."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Correct any drifted balance to the recomputed value.",
        )

    def handle(self, *args, **options):
        fix = options["fix"]
        drift_found = False

        for account in Account.objects.order_by("pk"):
            expected = self._expected_balance(account)
            drift = account.balance - expected
            if drift == 0:
                continue

            drift_found = True
            self.stdout.write(
                self.style.WARNING(
                    f"Account #{account.pk} ({account.name}, user={account.user_id}): "
                    f"stored={account.balance} expected={expected} drift={drift}"
                )
            )
            if fix:
                with db_transaction.atomic():
                    locked = Account.objects.select_for_update().get(pk=account.pk)
                    locked.balance = expected
                    locked.save(update_fields=["balance", "updated_at"])
                self.stdout.write(self.style.SUCCESS(f"  fixed -> {expected}"))

        if not drift_found:
            self.stdout.write(self.style.SUCCESS("No drift found."))
        elif not fix:
            sys.exit(1)

    def _expected_balance(self, account):
        primary = Transaction.objects.filter(account=account).aggregate(
            total=Sum(signed_amount_expression())
        )["total"] or Decimal("0.00")
        incoming_transfers = Transaction.objects.filter(
            transfer_to_account=account, type=TransactionType.TRANSFER
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        return account.opening_balance + primary + incoming_transfers
