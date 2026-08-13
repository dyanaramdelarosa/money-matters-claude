import pytest
from django.core.exceptions import ValidationError

from apps.categories.models import CategoryKind
from apps.transactions.models import Transaction, TransactionType
from tests.factories import AccountFactory, CategoryFactory, ProfileFactory

pytestmark = pytest.mark.django_db


def test_self_transfer_is_rejected():
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.TRANSFER,
        amount="10.00",
        currency=profile.base_currency,
        account=account,
        transfer_to_account=account,
    )

    with pytest.raises(ValidationError):
        txn.full_clean()


def test_transfer_requires_a_destination_account():
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.TRANSFER,
        amount="10.00",
        currency=profile.base_currency,
        account=account,
    )

    with pytest.raises(ValidationError):
        txn.full_clean()


def test_transfer_destination_must_belong_to_the_same_user():
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    other_account = AccountFactory(user=other_profile.user, currency=other_profile.base_currency)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.TRANSFER,
        amount="10.00",
        currency=profile.base_currency,
        account=account,
        transfer_to_account=other_account,
    )

    with pytest.raises(ValidationError):
        txn.full_clean()


def test_transfer_currency_must_match_destination_account_currency():
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    destination = AccountFactory(user=profile.user, currency=profile.base_currency)
    # Force a currency mismatch that could only arise from a future multi-currency
    # account, since a single-currency profile can't naturally produce this today.
    destination.currency = "EUR" if profile.base_currency != "EUR" else "USD"
    destination.save(update_fields=["currency"])
    txn = Transaction(
        user=profile.user,
        type=TransactionType.TRANSFER,
        amount="10.00",
        currency=profile.base_currency,
        account=account,
        transfer_to_account=destination,
    )

    with pytest.raises(ValidationError):
        txn.full_clean()


def test_str_includes_type_amount_and_date():
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.EXPENSE,
        amount="10.00",
        currency=profile.base_currency,
        account=account,
        category=category,
        date="2026-01-15",
    )

    assert str(txn) == "Expense 10.00 (2026-01-15)"


def test_transfer_cannot_have_a_category():
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    destination = AccountFactory(user=profile.user, currency=profile.base_currency)
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.TRANSFER,
        amount="10.00",
        currency=profile.base_currency,
        account=account,
        transfer_to_account=destination,
        category=category,
    )

    with pytest.raises(ValidationError):
        txn.full_clean()


def test_expense_requires_a_category():
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.EXPENSE,
        amount="10.00",
        currency=profile.base_currency,
        account=account,
    )

    with pytest.raises(ValidationError):
        txn.full_clean()


def test_expense_category_kind_must_match_transaction_type():
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    income_category = CategoryFactory(user=profile.user, kind=CategoryKind.INCOME)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.EXPENSE,
        amount="10.00",
        currency=profile.base_currency,
        account=account,
        category=income_category,
    )

    with pytest.raises(ValidationError):
        txn.full_clean()


def test_non_transfer_cannot_set_a_destination_account():
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    other_account = AccountFactory(user=profile.user, currency=profile.base_currency)
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.EXPENSE,
        amount="10.00",
        currency=profile.base_currency,
        account=account,
        transfer_to_account=other_account,
        category=category,
    )

    with pytest.raises(ValidationError):
        txn.full_clean()


def test_account_must_belong_to_the_same_user():
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    account = AccountFactory(user=other_profile.user, currency=other_profile.base_currency)
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.EXPENSE,
        amount="10.00",
        currency=other_profile.base_currency,
        account=account,
        category=category,
    )

    with pytest.raises(ValidationError):
        txn.full_clean()


def test_currency_must_match_account_currency():
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.EXPENSE,
        amount="10.00",
        currency="EUR",
        account=account,
        category=category,
    )

    with pytest.raises(ValidationError):
        txn.full_clean()


def test_amount_must_be_positive():
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.EXPENSE,
        amount="0.00",
        currency=profile.base_currency,
        account=account,
        category=category,
    )

    with pytest.raises(ValidationError):
        txn.full_clean()


def test_transfer_amount_must_be_positive():
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    destination = AccountFactory(user=profile.user, currency=profile.base_currency)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.TRANSFER,
        amount="0.00",
        currency=profile.base_currency,
        account=account,
        transfer_to_account=destination,
    )

    with pytest.raises(ValidationError):
        txn.full_clean()


def test_valid_expense_passes_clean():
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.EXPENSE,
        amount="10.00",
        currency=profile.base_currency,
        account=account,
        category=category,
    )

    txn.full_clean()


def test_valid_transfer_passes_clean():
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    destination = AccountFactory(user=profile.user, currency=profile.base_currency)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.TRANSFER,
        amount="10.00",
        currency=profile.base_currency,
        account=account,
        transfer_to_account=destination,
    )

    txn.full_clean()


def test_adjustment_amount_can_be_negative():
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.ADJUSTMENT,
        amount="-15.00",
        currency=profile.base_currency,
        account=account,
    )

    txn.full_clean()


def test_adjustment_amount_cannot_be_zero():
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.ADJUSTMENT,
        amount="0.00",
        currency=profile.base_currency,
        account=account,
    )

    with pytest.raises(ValidationError):
        txn.full_clean()


def test_adjustment_cannot_have_a_category():
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.ADJUSTMENT,
        amount="15.00",
        currency=profile.base_currency,
        account=account,
        category=category,
    )

    with pytest.raises(ValidationError):
        txn.full_clean()


def test_adjustment_cannot_have_a_destination_account():
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    other = AccountFactory(user=profile.user, currency=profile.base_currency)
    txn = Transaction(
        user=profile.user,
        type=TransactionType.ADJUSTMENT,
        amount="15.00",
        currency=profile.base_currency,
        account=account,
        transfer_to_account=other,
    )

    with pytest.raises(ValidationError):
        txn.full_clean()
