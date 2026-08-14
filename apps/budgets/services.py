import calendar
from decimal import Decimal

from django.db import transaction as db_transaction
from django.db.models import Sum
from django.utils import timezone

from apps.transactions.models import Transaction, TransactionType

from .models import BudgetPeriod, BudgetScope


def period_bounds(scope, for_date):
    """The (start, end) dates of the period containing for_date, for a given
    BudgetScope. SEMI_MONTHLY is exactly the spec's 1st-15th / 16th-end-of-month
    split; monthrange handles 28/29/30/31-day months and leap years.
    """
    last_day = calendar.monthrange(for_date.year, for_date.month)[1]
    if scope == BudgetScope.MONTHLY:
        return for_date.replace(day=1), for_date.replace(day=last_day)
    if scope == BudgetScope.SEMI_MONTHLY:
        if for_date.day <= 15:
            return for_date.replace(day=1), for_date.replace(day=15)
        return for_date.replace(day=16), for_date.replace(day=last_day)
    if scope == BudgetScope.ANNUAL:
        return for_date.replace(month=1, day=1), for_date.replace(month=12, day=31)
    raise ValueError(f"Unknown scope: {scope}")


def get_or_create_period(definition, for_date=None):
    """Materializes the BudgetPeriod for the period containing for_date
    (default today), snapshotting the definition's current amount if it
    doesn't exist yet. Reused on every later read of that same period, so
    once created its amount is frozen until update_definition_amount()
    explicitly re-syncs it (only while the period is still open).
    """
    for_date = for_date or timezone.localdate()
    start, end = period_bounds(definition.scope, for_date)
    period, _ = BudgetPeriod.objects.get_or_create(
        definition=definition,
        period_start=start,
        defaults={"period_end": end, "user": definition.user, "amount": definition.amount},
    )
    return period


def update_definition_amount(definition, new_amount):
    """Editing affects the current (open) period and any future ones
    immediately; already-closed periods (period_end < today) are left
    untouched — that's what makes historical reports immutable.
    """
    today = timezone.localdate()
    with db_transaction.atomic():
        definition.amount = new_amount
        definition.full_clean()
        definition.save(update_fields=["amount", "updated_at"])
        BudgetPeriod.objects.filter(definition=definition, period_end__gte=today).update(
            amount=new_amount
        )
    return definition


def spent_for_period(period):
    qs = Transaction.objects.filter(
        user=period.user,
        type=TransactionType.EXPENSE,
        date__gte=period.period_start,
        date__lte=period.period_end,
    )
    if period.definition.category_id:
        qs = qs.filter(category_id=period.definition.category_id)
    return qs.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
