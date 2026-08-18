from django.db import transaction as db_transaction
from django.db.models import Case, DecimalField, F, When

from .models import Transaction, TransactionType


def signed_amount_expression():
    """The signed balance delta for a transaction's primary `account` leg
    (positive for INCOME/ADJUSTMENT, negative for EXPENSE/TRANSFER-out) as a
    DB expression, for use inside Sum(...) aggregates. A TRANSFER's
    destination leg is always a plain +amount on `transfer_to_account` and
    isn't part of this expression — see reconcile_balances._expected_balance()
    and apps.analytics.services.account_balance_history() for how callers add
    that second leg in separately.
    """
    return Case(
        When(type__in=[TransactionType.INCOME, TransactionType.ADJUSTMENT], then=F("amount")),
        default=-F("amount"),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )


def _apply(effects):
    for account, delta in sorted(effects, key=lambda effect: effect[0].pk):
        account.adjust_balance(delta)


def create_transaction(instance):
    with db_transaction.atomic():
        instance.full_clean()
        instance.save()
        _apply(instance._effects())
    return instance


def update_transaction(instance):
    with db_transaction.atomic():
        old = Transaction.objects.select_for_update().get(pk=instance.pk)
        old_effects = old._effects()
        instance.full_clean()
        instance.save()
        _apply([(account, -delta) for account, delta in old_effects])
        _apply(instance._effects())
    return instance


def delete_transaction(instance):
    with db_transaction.atomic():
        locked = Transaction.objects.select_for_update().get(pk=instance.pk)
        effects = locked._effects()
        instance.delete()
        _apply([(account, -delta) for account, delta in effects])
