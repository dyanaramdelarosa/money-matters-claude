from datetime import date, timedelta
from decimal import Decimal

import pytest
from freezegun import freeze_time

from apps.analytics import services
from apps.budgets.models import BudgetScope
from apps.categories.models import CategoryKind
from apps.transactions import services as transaction_services
from apps.transactions.models import Transaction, TransactionType
from tests.factories import (
    AccountFactory,
    BudgetDefinitionFactory,
    CategoryFactory,
    ProfileFactory,
)

pytestmark = pytest.mark.django_db


def _txn(user, account, type_, amount, txn_date, category=None, transfer_to_account=None):
    txn = Transaction(
        user=user,
        type=type_,
        amount=amount,
        currency=account.currency,
        date=txn_date,
        account=account,
        category=category,
        transfer_to_account=transfer_to_account,
    )
    transaction_services.create_transaction(txn)
    return txn


class TestResolveRange:
    def test_defaults_to_current_month_to_date(self):
        with freeze_time("2026-06-15"):
            assert services.resolve_range(None, None) == (date(2026, 6, 1), date(2026, 6, 15))

    def test_missing_one_bound_still_applies_the_default(self):
        with freeze_time("2026-06-15"):
            assert services.resolve_range(date(2026, 5, 1), None) == (
                date(2026, 6, 1),
                date(2026, 6, 15),
            )

    def test_swaps_reversed_bounds(self):
        assert services.resolve_range(date(2026, 6, 10), date(2026, 6, 1)) == (
            date(2026, 6, 1),
            date(2026, 6, 10),
        )


class TestBucketSizeForRange:
    def test_60_day_range_is_daily(self):
        assert services.bucket_size_for_range(date(2026, 1, 1), date(2026, 3, 1)) == "day"

    def test_61_day_range_is_weekly(self):
        assert services.bucket_size_for_range(date(2026, 1, 1), date(2026, 3, 2)) == "week"

    def test_180_day_range_is_weekly(self):
        assert services.bucket_size_for_range(date(2026, 1, 1), date(2026, 6, 29)) == "week"

    def test_181_day_range_is_monthly(self):
        assert services.bucket_size_for_range(date(2026, 1, 1), date(2026, 6, 30)) == "month"


class TestBucketBoundaries:
    def test_day_boundaries_include_every_date(self):
        boundaries = services.bucket_boundaries(date(2026, 6, 1), date(2026, 6, 5), "day")
        assert boundaries == [date(2026, 6, d) for d in range(1, 6)]

    def test_week_boundaries_are_mondays_covering_the_range(self):
        boundaries = services.bucket_boundaries(date(2026, 6, 3), date(2026, 6, 20), "week")
        assert all(b.weekday() == 0 for b in boundaries)
        assert boundaries[0] <= date(2026, 6, 3) <= boundaries[0] + timedelta(days=6)
        assert boundaries[-1] <= date(2026, 6, 20)

    def test_month_boundaries_are_first_of_month(self):
        boundaries = services.bucket_boundaries(date(2026, 1, 15), date(2026, 3, 10), "month")
        assert boundaries == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]


def test_expense_by_category_series_sums_correctly_and_excludes_out_of_scope_rows():
    profile = ProfileFactory()
    user = profile.user
    account = AccountFactory(user=user, currency=profile.base_currency)
    groceries = CategoryFactory(user=user, kind=CategoryKind.EXPENSE)
    transport = CategoryFactory(user=user, kind=CategoryKind.EXPENSE)
    income_category = CategoryFactory(user=user, kind=CategoryKind.INCOME)

    _txn(
        user, account, TransactionType.EXPENSE, Decimal("10"), date(2026, 6, 2), category=groceries
    )
    _txn(user, account, TransactionType.EXPENSE, Decimal("5"), date(2026, 6, 3), category=groceries)
    _txn(user, account, TransactionType.EXPENSE, Decimal("7"), date(2026, 6, 2), category=transport)
    _txn(
        user, account, TransactionType.EXPENSE, Decimal("999"), date(2026, 7, 1), category=groceries
    )
    _txn(
        user,
        account,
        TransactionType.INCOME,
        Decimal("999"),
        date(2026, 6, 2),
        category=income_category,
    )

    data = services.expense_by_category_series(user, date(2026, 6, 1), date(2026, 6, 5))

    assert set(data["series"].keys()) == {groceries.name, transport.name}
    assert data["series"][groceries.name] == [
        Decimal("0.00"),
        Decimal("10"),
        Decimal("5"),
        Decimal("0.00"),
        Decimal("0.00"),
    ]
    assert data["series"][transport.name] == [
        Decimal("0.00"),
        Decimal("7"),
        Decimal("0.00"),
        Decimal("0.00"),
        Decimal("0.00"),
    ]


def test_income_vs_expense_series_sums_by_bucket_and_excludes_transfers():
    profile = ProfileFactory()
    user = profile.user
    account = AccountFactory(user=user, currency=profile.base_currency)
    other_account = AccountFactory(user=user, currency=profile.base_currency)
    expense_category = CategoryFactory(user=user, kind=CategoryKind.EXPENSE)
    income_category = CategoryFactory(user=user, kind=CategoryKind.INCOME)

    _txn(
        user,
        account,
        TransactionType.INCOME,
        Decimal("100"),
        date(2026, 6, 1),
        category=income_category,
    )
    _txn(
        user,
        account,
        TransactionType.EXPENSE,
        Decimal("40"),
        date(2026, 6, 1),
        category=expense_category,
    )
    _txn(
        user,
        account,
        TransactionType.EXPENSE,
        Decimal("10"),
        date(2026, 6, 2),
        category=expense_category,
    )
    _txn(
        user,
        account,
        TransactionType.TRANSFER,
        Decimal("5"),
        date(2026, 6, 1),
        transfer_to_account=other_account,
    )

    data = services.income_vs_expense_series(user, date(2026, 6, 1), date(2026, 6, 2))

    assert data["income"] == [Decimal("100"), Decimal("0.00")]
    assert data["expense"] == [Decimal("40"), Decimal("10")]


def test_net_cash_flow_series_is_income_minus_expense():
    profile = ProfileFactory()
    user = profile.user
    account = AccountFactory(user=user, currency=profile.base_currency)
    expense_category = CategoryFactory(user=user, kind=CategoryKind.EXPENSE)
    income_category = CategoryFactory(user=user, kind=CategoryKind.INCOME)

    _txn(
        user,
        account,
        TransactionType.INCOME,
        Decimal("100"),
        date(2026, 6, 1),
        category=income_category,
    )
    _txn(
        user,
        account,
        TransactionType.EXPENSE,
        Decimal("40"),
        date(2026, 6, 1),
        category=expense_category,
    )
    _txn(
        user,
        account,
        TransactionType.EXPENSE,
        Decimal("10"),
        date(2026, 6, 2),
        category=expense_category,
    )

    data = services.net_cash_flow_series(user, date(2026, 6, 1), date(2026, 6, 2))

    assert data["net"] == [Decimal("60"), Decimal("-10")]


def test_top_spending_categories_orders_desc_and_respects_limit():
    profile = ProfileFactory()
    user = profile.user
    account = AccountFactory(user=user, currency=profile.base_currency)
    low = CategoryFactory(user=user, kind=CategoryKind.EXPENSE)
    high = CategoryFactory(user=user, kind=CategoryKind.EXPENSE)
    mid = CategoryFactory(user=user, kind=CategoryKind.EXPENSE)
    _txn(user, account, TransactionType.EXPENSE, Decimal("10"), date(2026, 6, 1), category=low)
    _txn(user, account, TransactionType.EXPENSE, Decimal("50"), date(2026, 6, 1), category=high)
    _txn(user, account, TransactionType.EXPENSE, Decimal("30"), date(2026, 6, 1), category=mid)

    rows = services.top_spending_categories(user, date(2026, 6, 1), date(2026, 6, 1), limit=2)

    assert [row["category__name"] for row in rows] == [high.name, mid.name]


def test_account_balance_history_tracks_running_balance_including_transfer_and_opening_balance():
    profile = ProfileFactory()
    user = profile.user
    source = AccountFactory(
        user=user, currency=profile.base_currency, opening_balance=Decimal("100")
    )
    dest = AccountFactory(user=user, currency=profile.base_currency, opening_balance=Decimal("50"))
    category = CategoryFactory(user=user, kind=CategoryKind.EXPENSE)

    # Before the range — must be folded into balance_before_range, not shown as its own delta.
    _txn(user, source, TransactionType.EXPENSE, Decimal("20"), date(2026, 5, 15), category=category)
    # Within range.
    _txn(
        user,
        source,
        TransactionType.TRANSFER,
        Decimal("30"),
        date(2026, 6, 2),
        transfer_to_account=dest,
    )
    _txn(user, source, TransactionType.EXPENSE, Decimal("10"), date(2026, 6, 3), category=category)

    data = services.account_balance_history(user, date(2026, 6, 1), date(2026, 6, 5))
    source_series = next(a for a in data["accounts"] if a["account"] == source.name)
    dest_series = next(a for a in data["accounts"] if a["account"] == dest.name)

    def at(series, d):
        return series["values"][data["buckets"].index(d)]

    assert at(source_series, date(2026, 6, 1)) == Decimal("80")
    assert at(source_series, date(2026, 6, 2)) == Decimal("50")
    assert at(source_series, date(2026, 6, 3)) == Decimal("40")
    assert at(source_series, date(2026, 6, 5)) == Decimal("40")

    assert at(dest_series, date(2026, 6, 1)) == Decimal("50")
    assert at(dest_series, date(2026, 6, 2)) == Decimal("80")
    assert at(dest_series, date(2026, 6, 5)) == Decimal("80")


def test_budget_vs_actual_matches_spent_for_period_for_category_and_overall_budgets():
    profile = ProfileFactory()
    user = profile.user

    with freeze_time("2026-06-15"):
        category_budget = BudgetDefinitionFactory(
            user=user, scope=BudgetScope.MONTHLY, amount=Decimal("500")
        )
        BudgetDefinitionFactory(
            user=user, category=None, scope=BudgetScope.MONTHLY, amount=Decimal("1000")
        )
        account = AccountFactory(user=user, currency=profile.base_currency)
        _txn(
            user,
            account,
            TransactionType.EXPENSE,
            Decimal("50"),
            date(2026, 6, 5),
            category=category_budget.category,
        )

        rows = services.budget_vs_actual(user)

    category_row = next(r for r in rows if r["label"] == category_budget.category.name)
    overall_row = next(r for r in rows if r["label"] == "Overall")

    assert category_row["budgeted"] == Decimal("500")
    assert category_row["spent"] == Decimal("50")
    assert category_row["remaining"] == Decimal("450")
    assert category_row["period_start"] == date(2026, 6, 1)
    assert category_row["scope_label"] == "Monthly"
    assert category_row["period_end"] == date(2026, 6, 30)
    assert overall_row["budgeted"] == Decimal("1000")
    assert overall_row["spent"] == Decimal("50")


def test_budget_vs_actual_reports_the_current_period_bounds_for_semi_monthly_scope():
    profile = ProfileFactory()
    user = profile.user

    with freeze_time("2026-06-20"):
        definition = BudgetDefinitionFactory(
            user=user, scope=BudgetScope.SEMI_MONTHLY, amount=Decimal("500")
        )
        account = AccountFactory(user=user, currency=profile.base_currency)
        # Spent in the now-closed first half of the month — must not count
        # against the current (second-half) period's total.
        _txn(
            user,
            account,
            TransactionType.EXPENSE,
            Decimal("50"),
            date(2026, 6, 5),
            category=definition.category,
        )

        rows = services.budget_vs_actual(user)

    row = rows[0]
    assert row["scope_label"] == "Semi-monthly"
    assert row["period_start"] == date(2026, 6, 16)
    assert row["period_end"] == date(2026, 6, 30)
    assert row["spent"] == Decimal("0.00")


def test_budget_vs_actual_date_to_selects_the_period_covering_that_date():
    """A caller-supplied `date_to` (the analytics filter's end date, with no
    `date_from` — a single-day "as of" query) picks which period a
    semi-monthly budget reports, not just the current-today one — this is
    what lets the dashboard show the first-half period's actual spend when
    the user filters to a first-half date range.
    """
    profile = ProfileFactory()
    user = profile.user

    with freeze_time("2026-06-20"):
        definition = BudgetDefinitionFactory(
            user=user, scope=BudgetScope.SEMI_MONTHLY, amount=Decimal("500")
        )
        account = AccountFactory(user=user, currency=profile.base_currency)
        _txn(
            user,
            account,
            TransactionType.EXPENSE,
            Decimal("50"),
            date(2026, 6, 5),
            category=definition.category,
        )

        rows = services.budget_vs_actual(user, date_to=date(2026, 6, 10))

    row = rows[0]
    assert row["period_start"] == date(2026, 6, 1)
    assert row["period_end"] == date(2026, 6, 15)
    assert row["spent"] == Decimal("50.00")
    assert row["scope_label"] == "Semi-monthly"


def test_budget_vs_actual_sums_both_halves_when_the_range_spans_the_whole_month():
    """A semi-monthly budget's range no longer fits in one half once it spans
    the whole month (e.g. the dashboard's default "this month" view, or an
    explicit Month/Quarter/Year preset) — both halves get materialized and
    their budgeted/spent figures summed, "monthly level" instead of showing
    just whichever half date_to lands in.
    """
    profile = ProfileFactory()
    user = profile.user

    with freeze_time("2026-06-20"):
        definition = BudgetDefinitionFactory(
            user=user,
            scope=BudgetScope.SEMI_MONTHLY,
            amount=Decimal("20000"),
            second_half_amount=Decimal("10000"),
        )
        account = AccountFactory(user=user, currency=profile.base_currency)
        _txn(
            user,
            account,
            TransactionType.EXPENSE,
            Decimal("15000"),
            date(2026, 6, 5),
            category=definition.category,
        )
        _txn(
            user,
            account,
            TransactionType.EXPENSE,
            Decimal("3000"),
            date(2026, 6, 20),
            category=definition.category,
        )

        rows = services.budget_vs_actual(
            user, date_from=date(2026, 6, 1), date_to=date(2026, 6, 30)
        )

    row = rows[0]
    assert row["budgeted"] == Decimal("30000")
    assert row["spent"] == Decimal("18000")
    assert row["remaining"] == Decimal("12000")
    assert row["period_start"] == date(2026, 6, 1)
    assert row["period_end"] == date(2026, 6, 30)
    assert row["scope_label"] == "Semi-monthly (combined)"


def test_budget_vs_actual_monthly_scope_is_unaffected_by_a_range_within_the_same_month():
    profile = ProfileFactory()
    user = profile.user

    with freeze_time("2026-06-15"):
        BudgetDefinitionFactory(user=user, scope=BudgetScope.MONTHLY, amount=Decimal("500"))

        rows = services.budget_vs_actual(
            user, date_from=date(2026, 6, 1), date_to=date(2026, 6, 15)
        )

    row = rows[0]
    assert row["budgeted"] == Decimal("500")
    assert row["period_start"] == date(2026, 6, 1)
    assert row["period_end"] == date(2026, 6, 30)
    assert row["scope_label"] == "Monthly"


def test_budget_vs_actual_monthly_scope_sums_across_months_for_a_year_range():
    """A Year-preset range spans several Monthly periods, not just one — each
    month the range touches gets summed, the same "combined" treatment a
    wide Semi-monthly range already gets.
    """
    profile = ProfileFactory()
    user = profile.user

    with freeze_time("2026-01-15"):
        definition = BudgetDefinitionFactory(
            user=user, scope=BudgetScope.MONTHLY, amount=Decimal("12000")
        )
        account = AccountFactory(user=user, currency=profile.base_currency)

    _txn(
        user,
        account,
        TransactionType.EXPENSE,
        Decimal("1000"),
        date(2026, 1, 5),
        category=definition.category,
    )
    _txn(
        user,
        account,
        TransactionType.EXPENSE,
        Decimal("2000"),
        date(2026, 3, 5),
        category=definition.category,
    )

    with freeze_time("2026-06-15"):
        rows = services.budget_vs_actual(
            user, date_from=date(2026, 1, 1), date_to=date(2026, 6, 15)
        )

    row = rows[0]
    assert row["budgeted"] == Decimal("72000")  # 12000 x 6 months (Jan-Jun)
    assert row["spent"] == Decimal("3000")
    assert row["period_start"] == date(2026, 1, 1)
    assert row["period_end"] == date(2026, 6, 30)
    assert row["scope_label"] == "Monthly (combined)"


def test_budget_vs_actual_annual_scope_sums_across_years_for_a_multi_year_range():
    profile = ProfileFactory()
    user = profile.user

    with freeze_time("2025-06-15"):
        BudgetDefinitionFactory(user=user, scope=BudgetScope.ANNUAL, amount=Decimal("100000"))

    with freeze_time("2026-06-15"):
        rows = services.budget_vs_actual(
            user, date_from=date(2025, 1, 1), date_to=date(2026, 12, 31)
        )

    row = rows[0]
    assert row["budgeted"] == Decimal("200000")
    assert row["period_start"] == date(2025, 1, 1)
    assert row["period_end"] == date(2026, 12, 31)
    assert row["scope_label"] == "Annual (combined)"


def test_budget_vs_actual_reports_the_snapshotted_second_half_amount():
    profile = ProfileFactory()
    user = profile.user

    with freeze_time("2026-06-05"):
        BudgetDefinitionFactory(
            user=user,
            scope=BudgetScope.SEMI_MONTHLY,
            amount=Decimal("20000"),
            second_half_amount=Decimal("10000"),
        )

    with freeze_time("2026-06-20"):
        rows = services.budget_vs_actual(user)

    assert rows[0]["budgeted"] == Decimal("10000")
