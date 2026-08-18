from datetime import date
from decimal import Decimal

import pytest
from freezegun import freeze_time

from apps.budgets import services
from apps.budgets.models import BudgetPeriod, BudgetScope
from apps.categories.models import CategoryKind
from apps.transactions import services as transaction_services
from apps.transactions.models import Transaction, TransactionType
from tests.factories import AccountFactory, BudgetDefinitionFactory, CategoryFactory, ProfileFactory

pytestmark = pytest.mark.django_db


class TestPeriodBounds:
    def test_monthly(self):
        assert services.period_bounds(BudgetScope.MONTHLY, date(2026, 2, 10)) == (
            date(2026, 2, 1),
            date(2026, 2, 28),
        )

    def test_monthly_leap_year(self):
        assert services.period_bounds(BudgetScope.MONTHLY, date(2028, 2, 10)) == (
            date(2028, 2, 1),
            date(2028, 2, 29),
        )

    def test_monthly_31_day_month(self):
        assert services.period_bounds(BudgetScope.MONTHLY, date(2026, 1, 15)) == (
            date(2026, 1, 1),
            date(2026, 1, 31),
        )

    def test_semi_monthly_first_half(self):
        assert services.period_bounds(BudgetScope.SEMI_MONTHLY, date(2026, 4, 1)) == (
            date(2026, 4, 1),
            date(2026, 4, 15),
        )

    def test_semi_monthly_second_half_30_day_month(self):
        assert services.period_bounds(BudgetScope.SEMI_MONTHLY, date(2026, 4, 30)) == (
            date(2026, 4, 16),
            date(2026, 4, 30),
        )

    def test_semi_monthly_second_half_leap_february(self):
        assert services.period_bounds(BudgetScope.SEMI_MONTHLY, date(2028, 2, 20)) == (
            date(2028, 2, 16),
            date(2028, 2, 29),
        )

    def test_annual(self):
        assert services.period_bounds(BudgetScope.ANNUAL, date(2026, 7, 4)) == (
            date(2026, 1, 1),
            date(2026, 12, 31),
        )


def test_get_or_create_period_reuses_existing_row():
    definition = BudgetDefinitionFactory(scope=BudgetScope.MONTHLY, amount=Decimal("500"))

    with freeze_time("2026-06-10"):
        first = services.get_or_create_period(definition)
        second = services.get_or_create_period(definition)

    assert first.pk == second.pk
    assert BudgetPeriod.objects.filter(definition=definition).count() == 1


def test_editing_amount_leaves_a_closed_period_untouched():
    definition = BudgetDefinitionFactory(scope=BudgetScope.MONTHLY, amount=Decimal("500"))

    with freeze_time("2026-06-15"):
        june_period = services.get_or_create_period(definition)
        assert june_period.amount == Decimal("500")

    with freeze_time("2026-07-01"):
        services.update_definition_amount(definition, Decimal("600"))
        july_period = services.get_or_create_period(definition)

    june_period.refresh_from_db()
    assert june_period.amount == Decimal("500")
    assert july_period.amount == Decimal("600")


def test_editing_amount_updates_the_current_open_period_immediately():
    definition = BudgetDefinitionFactory(scope=BudgetScope.MONTHLY, amount=Decimal("500"))

    with freeze_time("2026-06-10"):
        june_period = services.get_or_create_period(definition)
        assert june_period.amount == Decimal("500")

        services.update_definition_amount(definition, Decimal("650"))

        june_period.refresh_from_db()
        assert june_period.amount == Decimal("650")


def test_get_or_create_period_snapshots_second_half_amount_for_the_second_half():
    definition = BudgetDefinitionFactory(
        scope=BudgetScope.SEMI_MONTHLY, amount=Decimal("20000"), second_half_amount=Decimal("10000")
    )

    with freeze_time("2026-06-05"):
        first_half = services.get_or_create_period(definition)
    with freeze_time("2026-06-20"):
        second_half = services.get_or_create_period(definition)

    assert first_half.amount == Decimal("20000")
    assert second_half.amount == Decimal("10000")


def test_get_or_create_period_second_half_falls_back_to_amount_when_unset():
    definition = BudgetDefinitionFactory(scope=BudgetScope.SEMI_MONTHLY, amount=Decimal("500"))

    with freeze_time("2026-06-20"):
        second_half = services.get_or_create_period(definition)

    assert second_half.amount == Decimal("500")


def test_editing_second_half_amount_does_not_touch_an_already_open_first_half_period():
    definition = BudgetDefinitionFactory(scope=BudgetScope.SEMI_MONTHLY, amount=Decimal("20000"))

    with freeze_time("2026-06-05"):
        first_half = services.get_or_create_period(definition)
        services.update_definition_amount(definition, Decimal("20000"), Decimal("10000"))
        first_half.refresh_from_db()

        assert first_half.amount == Decimal("20000")

    with freeze_time("2026-06-20"):
        second_half = services.get_or_create_period(definition)
        assert second_half.amount == Decimal("10000")


def test_editing_amount_without_second_half_amount_clears_an_existing_split():
    definition = BudgetDefinitionFactory(
        scope=BudgetScope.SEMI_MONTHLY, amount=Decimal("20000"), second_half_amount=Decimal("10000")
    )

    with freeze_time("2026-06-20"):
        services.update_definition_amount(definition, Decimal("15000"))
        definition.refresh_from_db()
        period = services.get_or_create_period(definition)

    assert definition.second_half_amount is None
    assert period.amount == Decimal("15000")


def test_spent_for_period_sums_matching_category_expenses_only():
    profile = ProfileFactory()
    definition = BudgetDefinitionFactory(
        user=profile.user, scope=BudgetScope.MONTHLY, amount=Decimal("500")
    )
    other_category = CategoryFactory(user=definition.user, kind=CategoryKind.EXPENSE)

    with freeze_time("2026-06-15"):
        period = services.get_or_create_period(definition)

        _create_expense(definition.user, definition.category, Decimal("30"), date(2026, 6, 5))
        _create_expense(definition.user, definition.category, Decimal("20"), date(2026, 6, 20))
        # Outside the period — must not count.
        _create_expense(definition.user, definition.category, Decimal("999"), date(2026, 7, 1))
        # Different category — must not count.
        _create_expense(definition.user, other_category, Decimal("999"), date(2026, 6, 10))

        assert services.spent_for_period(period) == Decimal("50")


def test_spent_for_period_overall_budget_sums_all_expense_categories():
    profile = ProfileFactory()
    definition = BudgetDefinitionFactory(
        user=profile.user, category=None, scope=BudgetScope.MONTHLY
    )
    category_a = CategoryFactory(user=definition.user, kind=CategoryKind.EXPENSE)
    category_b = CategoryFactory(user=definition.user, kind=CategoryKind.EXPENSE)

    with freeze_time("2026-06-15"):
        period = services.get_or_create_period(definition)

        _create_expense(definition.user, category_a, Decimal("10"), date(2026, 6, 1))
        _create_expense(definition.user, category_b, Decimal("15"), date(2026, 6, 2))

        assert services.spent_for_period(period) == Decimal("25")


def _create_expense(user, category, amount, txn_date):
    account = AccountFactory(user=user, currency=user.profile.base_currency)
    txn = Transaction(
        user=user,
        type=TransactionType.EXPENSE,
        amount=amount,
        currency=user.profile.base_currency,
        date=txn_date,
        account=account,
        category=category,
    )
    transaction_services.create_transaction(txn)
    return txn
