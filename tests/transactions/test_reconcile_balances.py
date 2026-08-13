from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command

from apps.accounts.models import Account
from apps.categories.models import CategoryKind
from apps.transactions import services
from apps.transactions.models import Transaction, TransactionType
from tests.factories import AccountFactory, CategoryFactory, ProfileFactory

pytestmark = pytest.mark.django_db


def _create_expense(user, account, category, amount):
    txn = Transaction(
        user=user,
        type=TransactionType.EXPENSE,
        amount=Decimal(amount),
        currency=account.currency,
        account=account,
        category=category,
    )
    services.create_transaction(txn)
    return txn


def test_reports_no_drift_when_balances_are_correct():
    profile = ProfileFactory()
    account = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    _create_expense(profile.user, account, category, "30.00")

    out = StringIO()
    call_command("reconcile_balances", stdout=out)

    assert "No drift found" in out.getvalue()


def test_reconciles_transfers_correctly():
    profile = ProfileFactory()
    source = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    destination = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("20.00")
    )
    txn = Transaction(
        user=profile.user,
        type=TransactionType.TRANSFER,
        amount=Decimal("40.00"),
        currency=profile.base_currency,
        account=source,
        transfer_to_account=destination,
    )
    services.create_transaction(txn)

    out = StringIO()
    call_command("reconcile_balances", stdout=out)

    assert "No drift found" in out.getvalue()


def test_reports_drift_and_exits_nonzero_without_fix():
    profile = ProfileFactory()
    account = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    _create_expense(profile.user, account, category, "30.00")
    Account.objects.filter(pk=account.pk).update(balance=Decimal("999.00"))

    out = StringIO()
    with pytest.raises(SystemExit) as exc_info:
        call_command("reconcile_balances", stdout=out)

    assert exc_info.value.code == 1
    assert "drift=" in out.getvalue()
    account.refresh_from_db()
    assert account.balance == Decimal("999.00")


def test_reconciles_adjustments_correctly():
    profile = ProfileFactory()
    account = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    txn = Transaction(
        user=profile.user,
        type=TransactionType.ADJUSTMENT,
        amount=Decimal("-20.00"),
        currency=profile.base_currency,
        account=account,
    )
    services.create_transaction(txn)

    out = StringIO()
    call_command("reconcile_balances", stdout=out)

    assert "No drift found" in out.getvalue()


def test_fix_corrects_drifted_balance():
    profile = ProfileFactory()
    account = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    _create_expense(profile.user, account, category, "30.00")
    Account.objects.filter(pk=account.pk).update(balance=Decimal("999.00"))

    out = StringIO()
    call_command("reconcile_balances", "--fix", stdout=out)

    account.refresh_from_db()
    assert account.balance == Decimal("70.00")
    assert "fixed" in out.getvalue()
