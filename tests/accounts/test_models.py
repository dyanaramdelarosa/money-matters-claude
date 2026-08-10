import threading
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.test import TransactionTestCase

from apps.accounts.models import Account, AccountType
from tests.factories import AccountFactory, ProfileFactory

pytestmark = pytest.mark.django_db


def test_creating_an_account_sets_balance_to_opening_balance():
    profile = ProfileFactory()

    account = Account.objects.create(
        user=profile.user,
        name="Main Bank",
        type=AccountType.BANK,
        currency=profile.base_currency,
        opening_balance=Decimal("150.00"),
    )

    assert account.balance == Decimal("150.00")


def test_editing_opening_balance_after_creation_does_not_change_balance():
    profile = ProfileFactory()
    account = Account.objects.create(
        user=profile.user,
        name="Main Bank",
        type=AccountType.BANK,
        currency=profile.base_currency,
        opening_balance=Decimal("150.00"),
    )

    account.opening_balance = Decimal("999.00")
    account.save()
    account.refresh_from_db()

    assert account.balance == Decimal("150.00")


def test_adjust_balance_updates_balance_and_persists():
    account = AccountFactory(opening_balance=Decimal("100.00"))

    account.adjust_balance(Decimal("25.50"))
    account.refresh_from_db()

    assert account.balance == Decimal("125.50")


def test_adjust_balance_allows_negative_delta():
    account = AccountFactory(opening_balance=Decimal("100.00"))

    account.adjust_balance(Decimal("-40.00"))
    account.refresh_from_db()

    assert account.balance == Decimal("60.00")


def test_archive_sets_is_archived_and_archived_at():
    account = AccountFactory()
    assert account.archived_at is None

    account.archive()

    assert account.is_archived is True
    assert account.archived_at is not None


def test_active_and_archived_querysets():
    active_account = AccountFactory()
    archived_account = AccountFactory()
    archived_account.archive()

    assert active_account in Account.objects.active()
    assert archived_account not in Account.objects.active()
    assert archived_account in Account.objects.archived()


def test_currency_must_match_profile_base_currency():
    profile = ProfileFactory(base_currency="EUR")
    account = Account(
        user=profile.user,
        name="Mismatched",
        type=AccountType.BANK,
        currency="USD",
        opening_balance=Decimal("0.00"),
    )

    with pytest.raises(ValidationError):
        account.full_clean()


def test_duplicate_account_name_for_same_user_is_rejected():
    profile = ProfileFactory()
    Account.objects.create(
        user=profile.user,
        name="Wallet",
        type=AccountType.CASH,
        currency=profile.base_currency,
        opening_balance=Decimal("0.00"),
    )

    with pytest.raises(IntegrityError):
        Account.objects.create(
            user=profile.user,
            name="Wallet",
            type=AccountType.CASH,
            currency=profile.base_currency,
            opening_balance=Decimal("0.00"),
        )


def test_archiving_an_account_frees_its_name_for_reuse():
    profile = ProfileFactory()
    original = Account.objects.create(
        user=profile.user,
        name="Wallet",
        type=AccountType.CASH,
        currency=profile.base_currency,
        opening_balance=Decimal("0.00"),
    )
    original.archive()

    recreated = Account.objects.create(
        user=profile.user,
        name="Wallet",
        type=AccountType.CASH,
        currency=profile.base_currency,
        opening_balance=Decimal("0.00"),
    )

    assert recreated.pk != original.pk
    original.refresh_from_db()
    assert original.name == "Wallet"


class AdjustBalanceConcurrencyTest(TransactionTestCase):
    """Proves adjust_balance's select_for_update actually prevents a lost update
    under real concurrent writers, not just when called sequentially. Requires
    Postgres: SQLite has no real row locking and just raises "database is locked"
    under genuine thread contention instead of serializing, so this only runs
    against Postgres (CI; or locally with DATABASE_URL pointed at Postgres) — see
    CLAUDE.md's dev-environment gap note.
    """

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Row-locking concurrency is only meaningfully testable on Postgres")

    def test_concurrent_adjustments_do_not_lose_updates(self):
        profile = ProfileFactory()
        account = Account.objects.create(
            user=profile.user,
            name="Shared Account",
            type=AccountType.BANK,
            currency=profile.base_currency,
            opening_balance=Decimal("0.00"),
        )

        iterations = 25
        delta = Decimal("1.00")
        thread_count = 4

        def worker():
            for _ in range(iterations):
                Account.objects.get(pk=account.pk).adjust_balance(delta)

        threads = [threading.Thread(target=worker) for _ in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        account.refresh_from_db()
        assert account.balance == delta * iterations * thread_count
