from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.categories.models import CategoryKind
from apps.transactions import services
from apps.transactions.models import Transaction, TransactionType
from tests.factories import AccountFactory, CategoryFactory, ProfileFactory

pytestmark = pytest.mark.django_db


def test_create_expense_decreases_account_balance():
    profile = ProfileFactory()
    account = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.EXPENSE,
        amount=Decimal("30.00"),
        currency=profile.base_currency,
        account=account,
        category=category,
    )

    services.create_transaction(txn)

    account.refresh_from_db()
    assert account.balance == Decimal("70.00")


def test_create_income_increases_account_balance():
    profile = ProfileFactory()
    account = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    category = CategoryFactory(user=profile.user, kind=CategoryKind.INCOME)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.INCOME,
        amount=Decimal("50.00"),
        currency=profile.base_currency,
        account=account,
        category=category,
    )

    services.create_transaction(txn)

    account.refresh_from_db()
    assert account.balance == Decimal("150.00")


def test_create_transfer_moves_amount_between_accounts():
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

    source.refresh_from_db()
    destination.refresh_from_db()
    assert source.balance == Decimal("60.00")
    assert destination.balance == Decimal("60.00")


def test_create_transaction_runs_validation():
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    account = AccountFactory(user=other_profile.user, currency=other_profile.base_currency)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.EXPENSE,
        amount=Decimal("10.00"),
        currency=other_profile.base_currency,
        account=account,
    )

    with pytest.raises(ValidationError):
        services.create_transaction(txn)


def test_delete_expense_reverses_balance():
    profile = ProfileFactory()
    account = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.EXPENSE,
        amount=Decimal("30.00"),
        currency=profile.base_currency,
        account=account,
        category=category,
    )
    services.create_transaction(txn)

    services.delete_transaction(txn)

    account.refresh_from_db()
    assert account.balance == Decimal("100.00")
    assert not Transaction.objects.filter(pk=txn.pk).exists()


def test_delete_transfer_reverses_both_accounts():
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

    services.delete_transaction(txn)

    source.refresh_from_db()
    destination.refresh_from_db()
    assert source.balance == Decimal("100.00")
    assert destination.balance == Decimal("20.00")


def test_update_amount_applies_only_the_delta():
    profile = ProfileFactory()
    account = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.EXPENSE,
        amount=Decimal("50.00"),
        currency=profile.base_currency,
        account=account,
        category=category,
    )
    services.create_transaction(txn)
    account.refresh_from_db()
    assert account.balance == Decimal("50.00")

    txn.amount = Decimal("80.00")
    services.update_transaction(txn)

    account.refresh_from_db()
    assert account.balance == Decimal("20.00")


def test_update_moving_expense_to_a_different_account():
    profile = ProfileFactory()
    account_a = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    account_b = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.EXPENSE,
        amount=Decimal("30.00"),
        currency=profile.base_currency,
        account=account_a,
        category=category,
    )
    services.create_transaction(txn)

    txn.account = account_b
    services.update_transaction(txn)

    account_a.refresh_from_db()
    account_b.refresh_from_db()
    assert account_a.balance == Decimal("100.00")
    assert account_b.balance == Decimal("70.00")


def test_update_changing_type_from_expense_to_income_flips_sign():
    profile = ProfileFactory()
    account = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    expense_category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    income_category = CategoryFactory(user=profile.user, kind=CategoryKind.INCOME)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.EXPENSE,
        amount=Decimal("30.00"),
        currency=profile.base_currency,
        account=account,
        category=expense_category,
    )
    services.create_transaction(txn)
    account.refresh_from_db()
    assert account.balance == Decimal("70.00")

    txn.type = TransactionType.INCOME
    txn.category = income_category
    services.update_transaction(txn)

    account.refresh_from_db()
    assert account.balance == Decimal("130.00")


def test_update_transfer_amount_and_destination_account():
    profile = ProfileFactory()
    account_a = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    account_b = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    account_c = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    txn = Transaction(
        user=profile.user,
        type=TransactionType.TRANSFER,
        amount=Decimal("20.00"),
        currency=profile.base_currency,
        account=account_a,
        transfer_to_account=account_b,
    )
    services.create_transaction(txn)
    account_a.refresh_from_db()
    account_b.refresh_from_db()
    assert account_a.balance == Decimal("80.00")
    assert account_b.balance == Decimal("120.00")

    txn.amount = Decimal("50.00")
    txn.transfer_to_account = account_c
    services.update_transaction(txn)

    account_a.refresh_from_db()
    account_b.refresh_from_db()
    account_c.refresh_from_db()
    assert account_a.balance == Decimal("50.00")
    assert account_b.balance == Decimal("100.00")
    assert account_c.balance == Decimal("150.00")


def test_create_adjustment_applies_signed_delta_upward():
    profile = ProfileFactory()
    account = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    txn = Transaction(
        user=profile.user,
        type=TransactionType.ADJUSTMENT,
        amount=Decimal("25.00"),
        currency=profile.base_currency,
        account=account,
    )

    services.create_transaction(txn)

    account.refresh_from_db()
    assert account.balance == Decimal("125.00")


def test_create_adjustment_applies_signed_delta_downward():
    profile = ProfileFactory()
    account = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    txn = Transaction(
        user=profile.user,
        type=TransactionType.ADJUSTMENT,
        amount=Decimal("-40.00"),
        currency=profile.base_currency,
        account=account,
    )

    services.create_transaction(txn)

    account.refresh_from_db()
    assert account.balance == Decimal("60.00")


def test_delete_adjustment_reverses_balance():
    profile = ProfileFactory()
    account = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    txn = Transaction(
        user=profile.user,
        type=TransactionType.ADJUSTMENT,
        amount=Decimal("25.00"),
        currency=profile.base_currency,
        account=account,
    )
    services.create_transaction(txn)

    services.delete_transaction(txn)

    account.refresh_from_db()
    assert account.balance == Decimal("100.00")
