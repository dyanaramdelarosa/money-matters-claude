from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.db.models import Case, DecimalField, F, Sum, When
from django.db.models.functions import TruncMonth, TruncWeek
from django.utils import timezone

from apps.accounts.models import Account
from apps.budgets.models import BudgetDefinition, BudgetScope
from apps.budgets.services import get_or_create_period, spent_for_period
from apps.transactions.models import Transaction, TransactionType
from apps.transactions.services import signed_amount_expression

_TRUNC_FUNCTIONS = {"week": TruncWeek, "month": TruncMonth}


def _bucket_expression(size):
    """`Transaction.date` is already a plain DateField, so a "day" bucket
    needs no truncation at all — TruncDate is meant to collapse a
    DateTimeField down to its date and raises on a bare DateField input.
    """
    if size == "day":
        return F("date")
    return _TRUNC_FUNCTIONS[size]("date")


def resolve_range(date_from, date_to):
    """Defaults to current month-to-date when either bound is missing, and
    swaps the bounds if they arrive reversed — an analytics card degrading to
    a sane default is a better UX than a hard validation error blocking every
    card on the dashboard at once.
    """
    if not date_from or not date_to:
        today = timezone.localdate()
        return today.replace(day=1), today
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    return date_from, date_to


def bucket_size_for_range(date_from, date_to):
    span_days = (date_to - date_from).days + 1
    if span_days <= 60:
        return "day"
    if span_days <= 180:
        return "week"
    return "month"


def bucket_boundaries(date_from, date_to, size):
    """The full ordered list of bucket keys spanning the range, matching how
    Django's TruncDate/TruncWeek/TruncMonth key their groups (TruncWeek keys
    to that ISO week's Monday, TruncMonth to the 1st) — so a chart can show a
    real zero for an empty bucket instead of a gap, which a DB GROUP BY alone
    would silently omit.
    """
    if size == "day":
        boundaries = []
        current = date_from
        while current <= date_to:
            boundaries.append(current)
            current += timedelta(days=1)
        return boundaries
    if size == "week":
        boundaries = []
        current = date_from - timedelta(days=date_from.weekday())
        while current <= date_to:
            boundaries.append(current)
            current += timedelta(days=7)
        return boundaries
    boundaries = []
    year, month = date_from.year, date_from.month
    while date(year, month, 1) <= date_to:
        boundaries.append(date(year, month, 1))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return boundaries


def expense_by_category_series(user, date_from, date_to):
    size = bucket_size_for_range(date_from, date_to)
    buckets = bucket_boundaries(date_from, date_to, size)

    rows = (
        Transaction.objects.filter(
            user=user, type=TransactionType.EXPENSE, date__gte=date_from, date__lte=date_to
        )
        .annotate(bucket=_bucket_expression(size))
        .values("bucket", "category__name")
        .annotate(total=Sum("amount"))
    )

    series = defaultdict(lambda: dict.fromkeys(buckets, Decimal("0.00")))
    for row in rows:
        series[row["category__name"]][row["bucket"]] = row["total"]

    return {
        "buckets": buckets,
        "series": {name: [values[b] for b in buckets] for name, values in series.items()},
    }


def income_vs_expense_series(user, date_from, date_to):
    size = bucket_size_for_range(date_from, date_to)
    buckets = bucket_boundaries(date_from, date_to, size)
    decimal_field = DecimalField(max_digits=14, decimal_places=2)

    rows = (
        Transaction.objects.filter(
            user=user,
            type__in=[TransactionType.INCOME, TransactionType.EXPENSE],
            date__gte=date_from,
            date__lte=date_to,
        )
        .annotate(bucket=_bucket_expression(size))
        .values("bucket")
        .annotate(
            income=Sum(
                Case(
                    When(type=TransactionType.INCOME, then=F("amount")),
                    default=0,
                    output_field=decimal_field,
                )
            ),
            expense=Sum(
                Case(
                    When(type=TransactionType.EXPENSE, then=F("amount")),
                    default=0,
                    output_field=decimal_field,
                )
            ),
        )
    )
    by_bucket = {row["bucket"]: row for row in rows}

    income, expense = [], []
    for bucket in buckets:
        row = by_bucket.get(bucket)
        income.append(row["income"] if row else Decimal("0.00"))
        expense.append(row["expense"] if row else Decimal("0.00"))
    return {"buckets": buckets, "income": income, "expense": expense}


def net_cash_flow_series(user, date_from, date_to):
    data = income_vs_expense_series(user, date_from, date_to)
    net = [
        income - expense for income, expense in zip(data["income"], data["expense"], strict=True)
    ]
    return {"buckets": data["buckets"], "net": net}


def top_spending_categories(user, date_from, date_to, limit=5):
    return list(
        Transaction.objects.filter(
            user=user, type=TransactionType.EXPENSE, date__gte=date_from, date__lte=date_to
        )
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")[:limit]
    )


def account_balance_history(user, date_from, date_to):
    size = bucket_size_for_range(date_from, date_to)
    buckets = bucket_boundaries(date_from, date_to, size)

    result = []
    for account in Account.objects.filter(user=user).active():
        primary_before = Transaction.objects.filter(account=account, date__lt=date_from).aggregate(
            total=Sum(signed_amount_expression())
        )["total"] or Decimal("0.00")
        incoming_before = Transaction.objects.filter(
            transfer_to_account=account, type=TransactionType.TRANSFER, date__lt=date_from
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        balance_before = account.opening_balance + primary_before + incoming_before

        deltas = defaultdict(lambda: Decimal("0.00"))
        primary_rows = (
            Transaction.objects.filter(account=account, date__gte=date_from, date__lte=date_to)
            .annotate(bucket=_bucket_expression(size))
            .values("bucket")
            .annotate(total=Sum(signed_amount_expression()))
        )
        incoming_rows = (
            Transaction.objects.filter(
                transfer_to_account=account,
                type=TransactionType.TRANSFER,
                date__gte=date_from,
                date__lte=date_to,
            )
            .annotate(bucket=_bucket_expression(size))
            .values("bucket")
            .annotate(total=Sum("amount"))
        )
        for row in primary_rows:
            deltas[row["bucket"]] += row["total"]
        for row in incoming_rows:
            deltas[row["bucket"]] += row["total"]

        running = balance_before
        values = []
        for bucket in buckets:
            running += deltas[bucket]
            values.append(running)
        result.append({"account": account.name, "values": values})

    return {"buckets": buckets, "accounts": result}


def _next_period_start(scope, period_start):
    """The start date of the period immediately after the one starting on
    period_start, for a given scope — mirrors
    apps.budgets.services.period_bounds' own boundaries so walking forward
    from any period_start with this always lands exactly on the next one.
    """
    if scope == BudgetScope.SEMI_MONTHLY:
        if period_start.day == 1:
            return period_start.replace(day=16)
        year, month = period_start.year, period_start.month + 1
        if month > 12:
            month = 1
            year += 1
        return date(year, month, 1)
    if scope == BudgetScope.MONTHLY:
        year, month = period_start.year, period_start.month + 1
        if month > 12:
            month = 1
            year += 1
        return date(year, month, 1)
    if scope == BudgetScope.ANNUAL:
        return period_start.replace(year=period_start.year + 1)
    raise ValueError(f"Unknown scope: {scope}")


def _figures_for_range(definition, date_from, date_to):
    """A budget's budgeted/spent/period bounds for [date_from, date_to]. If
    the range fits inside a single period for the budget's own scope, that
    period's own snapshotted amount is used unchanged. A range spanning more
    than one period — a Month/Quarter/Year preset touching several Monthly
    periods, a range crossing a Semi-monthly half, or (rarer) a
    multi-year range against an Annual budget — no longer maps onto a single
    period, so every period it touches is materialized and summed, instead
    of showing just whichever single period `date_to` happens to land in.
    """
    first_period = get_or_create_period(definition, for_date=date_from)
    last_period = get_or_create_period(definition, for_date=date_to)
    if first_period.pk == last_period.pk:
        return first_period.amount, spent_for_period(first_period), first_period, False

    periods = [first_period]
    current = first_period
    while current.period_start < last_period.period_start:
        current = get_or_create_period(
            definition, for_date=_next_period_start(definition.scope, current.period_start)
        )
        periods.append(current)

    budgeted = sum((period.amount for period in periods), Decimal("0.00"))
    spent = sum((spent_for_period(period) for period in periods), Decimal("0.00"))
    combined = SimpleNamespace(
        period_start=periods[0].period_start, period_end=periods[-1].period_end
    )
    return budgeted, spent, combined, True


def budget_vs_actual(user, date_from=None, date_to=None):
    """Each active budget's figures for [date_from, date_to] (both default to
    today, so the no-argument call still reports "today's period" as
    before). A budget's own scope (SEMI_MONTHLY/MONTHLY/ANNUAL) still governs
    its period boundaries, but any budget whose scope's period is narrower
    than the selected range now sums every period the range touches (see
    `_figures_for_range`) rather than showing just one.
    """
    date_to = date_to or timezone.localdate()
    date_from = date_from or date_to
    rows = []
    definitions = BudgetDefinition.objects.filter(user=user).active().select_related("category")
    for definition in definitions:
        budgeted, spent, period, combined = _figures_for_range(definition, date_from, date_to)
        scope_label = definition.get_scope_display()
        if combined:
            scope_label += " (combined)"
        rows.append(
            {
                "label": definition.category.name if definition.category_id else "Overall",
                "budgeted": budgeted,
                "spent": spent,
                "remaining": budgeted - spent,
                "percent_used": (spent / budgeted * 100) if budgeted else None,
                "period_start": period.period_start,
                "period_end": period.period_end,
                "scope_label": scope_label,
            }
        )
    return rows
