from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.categories.models import CategoryKind
from apps.transactions import services as transaction_services
from apps.transactions.models import Transaction, TransactionType
from tests.factories import AccountFactory, BudgetDefinitionFactory, CategoryFactory, ProfileFactory

pytestmark = pytest.mark.django_db

CARD_URL_NAMES = [
    "analytics:card-expense-by-category",
    "analytics:card-income-expense-trend",
    "analytics:card-net-cash-flow",
    "analytics:card-top-categories",
    "analytics:card-account-balance-history",
    "analytics:card-budget-vs-actual",
]


def _expense(user, account, category, amount, txn_date=None):
    return _txn(user, account, TransactionType.EXPENSE, category, amount, txn_date)


def _income(user, account, category, amount, txn_date=None):
    return _txn(user, account, TransactionType.INCOME, category, amount, txn_date)


def _txn(user, account, type_, category, amount, txn_date=None):
    txn = Transaction(
        user=user,
        type=type_,
        amount=Decimal(amount),
        currency=account.currency,
        date=txn_date or timezone.localdate(),
        account=account,
        category=category,
    )
    transaction_services.create_transaction(txn)
    return txn


def test_dashboard_requires_login(client):
    response = client.get(reverse("analytics:dashboard"))

    assert response.status_code == 302
    assert reverse("account_login") in response.url


@pytest.mark.parametrize("url_name", CARD_URL_NAMES)
def test_card_requires_login(client, url_name):
    response = client.get(reverse(url_name))

    assert response.status_code == 302
    assert reverse("account_login") in response.url


def test_dashboard_includes_hx_get_urls_for_every_card(client):
    profile = ProfileFactory()
    client.force_login(profile.user)

    response = client.get(reverse("analytics:dashboard"))

    assert response.status_code == 200
    body = response.content.decode()
    for url_name in CARD_URL_NAMES:
        assert reverse(url_name) in body


def test_expense_by_category_card_only_shows_requesting_users_data(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    other_account = AccountFactory(user=other_profile.user, currency=other_profile.base_currency)
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    other_category = CategoryFactory(user=other_profile.user, kind=CategoryKind.EXPENSE)
    _expense(profile.user, account, category, "10")
    _expense(other_profile.user, other_account, other_category, "999")

    client.force_login(profile.user)
    response = client.get(reverse("analytics:card-expense-by-category"))

    body = response.content.decode()
    assert category.name in body
    assert other_category.name not in body


def test_account_balance_history_card_only_shows_requesting_users_accounts(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    other_account = AccountFactory(user=other_profile.user, currency=other_profile.base_currency)

    client.force_login(profile.user)
    response = client.get(reverse("analytics:card-account-balance-history"))

    body = response.content.decode()
    assert account.name in body
    assert other_account.name not in body


def test_budget_vs_actual_card_only_shows_requesting_users_budgets(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    budget = BudgetDefinitionFactory(user=profile.user)
    other_budget = BudgetDefinitionFactory(user=other_profile.user)

    client.force_login(profile.user)
    response = client.get(reverse("analytics:card-budget-vs-actual"))

    body = response.content.decode()
    assert budget.category.name in body
    assert other_budget.category.name not in body


def test_income_expense_trend_card_only_shows_requesting_users_data(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    other_account = AccountFactory(user=other_profile.user, currency=other_profile.base_currency)
    category = CategoryFactory(user=profile.user, kind=CategoryKind.INCOME)
    other_category = CategoryFactory(user=other_profile.user, kind=CategoryKind.INCOME)
    _income(profile.user, account, category, "100")
    _income(other_profile.user, other_account, other_category, "999")

    client.force_login(profile.user)
    response = client.get(
        reverse("analytics:card-income-expense-trend"),
        {
            "date_from": timezone.localdate().isoformat(),
            "date_to": timezone.localdate().isoformat(),
        },
    )

    assert response.status_code == 200
    body = response.content.decode()
    assert "100.0" in body
    assert "999.0" not in body


def test_net_cash_flow_card_renders_a_total_for_the_requesting_user(client):
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    category = CategoryFactory(user=profile.user, kind=CategoryKind.INCOME)
    _income(profile.user, account, category, "75")

    client.force_login(profile.user)
    response = client.get(reverse("analytics:card-net-cash-flow"))

    assert response.status_code == 200
    assert "75.00" in response.content.decode()


def test_top_categories_card_only_shows_requesting_users_data(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    other_account = AccountFactory(user=other_profile.user, currency=other_profile.base_currency)
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    other_category = CategoryFactory(user=other_profile.user, kind=CategoryKind.EXPENSE)
    _expense(profile.user, account, category, "15")
    _expense(other_profile.user, other_account, other_category, "999")

    client.force_login(profile.user)
    response = client.get(reverse("analytics:card-top-categories"))

    body = response.content.decode()
    assert category.name in body
    assert other_category.name not in body


def test_invalid_date_range_falls_back_to_current_month_instead_of_erroring(client):
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    _expense(profile.user, account, category, "25")

    client.force_login(profile.user)
    response = client.get(
        reverse("analytics:card-expense-by-category"),
        {"date_from": "not-a-date", "date_to": "2026-06-01"},
    )

    assert response.status_code == 200
    assert category.name in response.content.decode()
