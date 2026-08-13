from decimal import Decimal

import pytest
from django.urls import reverse

from apps.categories.models import CategoryKind
from apps.transactions import services
from apps.transactions.models import Transaction, TransactionType
from tests.factories import AccountFactory, CategoryFactory, ProfileFactory, TransactionFactory

pytestmark = pytest.mark.django_db


def test_list_view_requires_login(client):
    response = client.get(reverse("transactions:list"))

    assert response.status_code == 302
    assert reverse("account_login") in response.url


def test_list_view_only_shows_own_transactions(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    mine = TransactionFactory(user=profile.user)
    TransactionFactory(user=other_profile.user)

    client.force_login(profile.user)
    response = client.get(reverse("transactions:list"))

    assert list(response.context["transactions"]) == [mine]


def test_list_view_filters_by_date_range(client):
    profile = ProfileFactory()
    in_range = TransactionFactory(user=profile.user, date="2026-01-15")
    TransactionFactory(user=profile.user, date="2026-01-01")
    TransactionFactory(user=profile.user, date="2026-02-01")
    client.force_login(profile.user)

    response = client.get(
        reverse("transactions:list"), {"date_from": "2026-01-10", "date_to": "2026-01-31"}
    )

    assert list(response.context["transactions"]) == [in_range]


def test_list_view_filters_by_type(client):
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    income_category = CategoryFactory(user=profile.user, kind=CategoryKind.INCOME)
    TransactionFactory(user=profile.user)
    income = TransactionFactory(
        user=profile.user, type=TransactionType.INCOME, account=account, category=income_category
    )
    client.force_login(profile.user)

    response = client.get(reverse("transactions:list"), {"type": TransactionType.INCOME})

    assert list(response.context["transactions"]) == [income]


def test_list_view_filters_by_account_including_transfer_destination(client):
    profile = ProfileFactory()
    wallet = AccountFactory(user=profile.user, currency=profile.base_currency)
    bank = AccountFactory(user=profile.user, currency=profile.base_currency)
    other = AccountFactory(user=profile.user, currency=profile.base_currency)
    from_wallet = TransactionFactory(user=profile.user, account=wallet)
    transfer_into_wallet = Transaction.objects.create(
        user=profile.user,
        type=TransactionType.TRANSFER,
        amount=Decimal("10.00"),
        currency=profile.base_currency,
        account=bank,
        transfer_to_account=wallet,
    )
    TransactionFactory(user=profile.user, account=other)
    client.force_login(profile.user)

    response = client.get(reverse("transactions:list"), {"account": wallet.pk})

    assert set(response.context["transactions"]) == {from_wallet, transfer_into_wallet}


def test_list_view_filters_by_category(client):
    profile = ProfileFactory()
    category_a = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    category_b = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    matching = TransactionFactory(user=profile.user, category=category_a)
    TransactionFactory(user=profile.user, category=category_b)
    client.force_login(profile.user)

    response = client.get(reverse("transactions:list"), {"category": category_a.pk})

    assert list(response.context["transactions"]) == [matching]


def test_list_view_combined_filters(client):
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    matching = TransactionFactory(
        user=profile.user, account=account, category=category, date="2026-01-15"
    )
    TransactionFactory(user=profile.user, account=account, category=category, date="2026-03-01")
    client.force_login(profile.user)

    response = client.get(
        reverse("transactions:list"),
        {
            "account": account.pk,
            "category": category.pk,
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
        },
    )

    assert list(response.context["transactions"]) == [matching]


def test_list_view_invalid_filter_shows_form_error_and_ignores_filter(client):
    profile = ProfileFactory()
    mine = TransactionFactory(user=profile.user)
    client.force_login(profile.user)

    response = client.get(reverse("transactions:list"), {"date_from": "not-a-date"})

    assert response.status_code == 200
    assert "date_from" in response.context["filter_form"].errors
    assert list(response.context["transactions"]) == [mine]


def test_list_view_filtering_by_another_users_account_id_is_rejected(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    mine = TransactionFactory(user=profile.user)
    other_account = AccountFactory(user=other_profile.user, currency=other_profile.base_currency)
    client.force_login(profile.user)

    response = client.get(reverse("transactions:list"), {"account": other_account.pk})

    assert "account" in response.context["filter_form"].errors
    assert list(response.context["transactions"]) == [mine]


def test_list_view_filter_dropdowns_exclude_archived_account_and_category(client):
    profile = ProfileFactory()
    archived_account = AccountFactory(user=profile.user, currency=profile.base_currency)
    archived_account.archive()
    archived_category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    archived_category.archive()
    client.force_login(profile.user)

    response = client.get(reverse("transactions:list"))

    filter_form = response.context["filter_form"]
    assert archived_account not in filter_form.fields["account"].queryset
    assert archived_category not in filter_form.fields["category"].queryset


def test_list_view_filtering_by_archived_account_id_is_rejected(client):
    profile = ProfileFactory()
    mine = TransactionFactory(user=profile.user)
    archived_account = AccountFactory(user=profile.user, currency=profile.base_currency)
    archived_account.archive()
    client.force_login(profile.user)

    response = client.get(reverse("transactions:list"), {"account": archived_account.pk})

    assert "account" in response.context["filter_form"].errors
    assert list(response.context["transactions"]) == [mine]


def test_create_expense_via_view_adjusts_balance(client):
    profile = ProfileFactory()
    account = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    client.force_login(profile.user)

    response = client.post(
        reverse("transactions:create"),
        {
            "type": TransactionType.EXPENSE,
            "date": "2026-01-15",
            "amount": "25.00",
            "account": account.pk,
            "category": category.pk,
            "note": "",
            "receipt_reference": "",
        },
    )

    assert response.status_code == 302
    account.refresh_from_db()
    assert account.balance == Decimal("75.00")
    txn = Transaction.objects.get(user=profile.user)
    assert txn.currency == profile.base_currency


def test_create_transfer_via_view_moves_amount_between_accounts(client):
    profile = ProfileFactory()
    source = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    destination = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("20.00")
    )
    client.force_login(profile.user)

    response = client.post(
        reverse("transactions:create"),
        {
            "type": TransactionType.TRANSFER,
            "date": "2026-01-15",
            "amount": "40.00",
            "account": source.pk,
            "transfer_to_account": destination.pk,
            "note": "",
            "receipt_reference": "",
        },
    )

    assert response.status_code == 302
    source.refresh_from_db()
    destination.refresh_from_db()
    assert source.balance == Decimal("60.00")
    assert destination.balance == Decimal("60.00")


def test_create_with_missing_category_shows_form_error(client):
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    client.force_login(profile.user)

    response = client.post(
        reverse("transactions:create"),
        {
            "type": TransactionType.EXPENSE,
            "date": "2026-01-15",
            "amount": "25.00",
            "account": account.pk,
            "note": "",
            "receipt_reference": "",
        },
    )

    assert response.status_code == 200
    assert Transaction.objects.filter(user=profile.user).count() == 0


def test_archived_account_excluded_from_create_form_choices(client):
    profile = ProfileFactory()
    archived = AccountFactory(user=profile.user, currency=profile.base_currency)
    archived.archive()
    client.force_login(profile.user)

    response = client.get(reverse("transactions:create"))

    assert archived not in response.context["form"].fields["account"].queryset


def test_archived_category_excluded_from_create_form_choices(client):
    profile = ProfileFactory()
    archived = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    archived.archive()
    client.force_login(profile.user)

    response = client.get(reverse("transactions:create"))

    assert archived not in response.context["form"].fields["category"].queryset


def test_detail_view_404s_for_another_users_transaction(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    txn = TransactionFactory(user=other_profile.user)

    client.force_login(profile.user)
    response = client.get(reverse("transactions:detail", args=[txn.pk]))

    assert response.status_code == 404


def test_edit_view_updates_amount_and_reapplies_balance_effect(client):
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

    client.force_login(profile.user)
    response = client.post(
        reverse("transactions:edit", args=[txn.pk]),
        {
            "type": TransactionType.EXPENSE,
            "date": str(txn.date),
            "amount": "50.00",
            "account": account.pk,
            "category": category.pk,
            "note": "",
            "receipt_reference": "",
        },
    )

    assert response.status_code == 302
    account.refresh_from_db()
    assert account.balance == Decimal("50.00")


def test_edit_view_404s_for_another_users_transaction(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    txn = TransactionFactory(user=other_profile.user)

    client.force_login(profile.user)
    response = client.post(
        reverse("transactions:edit", args=[txn.pk]),
        {
            "type": TransactionType.EXPENSE,
            "date": str(txn.date),
            "amount": "999.00",
            "account": txn.account_id,
            "category": txn.category_id,
        },
    )

    assert response.status_code == 404


def test_delete_view_shows_confirm_page_then_reverses_balance_on_post(client):
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

    client.force_login(profile.user)
    get_response = client.get(reverse("transactions:delete", args=[txn.pk]))
    assert get_response.status_code == 200

    post_response = client.post(reverse("transactions:delete", args=[txn.pk]))

    assert post_response.status_code == 302
    account.refresh_from_db()
    assert account.balance == Decimal("100.00")
    assert not Transaction.objects.filter(pk=txn.pk).exists()


def test_delete_view_404s_for_another_users_transaction(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    txn = TransactionFactory(user=other_profile.user)

    client.force_login(profile.user)
    response = client.post(reverse("transactions:delete", args=[txn.pk]))

    assert response.status_code == 404
    assert Transaction.objects.filter(pk=txn.pk).exists()


def test_correct_balance_view_creates_adjustment_transaction(client):
    profile = ProfileFactory()
    account = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    client.force_login(profile.user)

    response = client.post(
        reverse("transactions:correct_balance", args=[account.pk]),
        {"new_balance": "175.00", "date": "2026-01-15", "note": "missed a week"},
    )

    assert response.status_code == 302
    account.refresh_from_db()
    assert account.balance == Decimal("175.00")
    txn = Transaction.objects.get(user=profile.user, type=TransactionType.ADJUSTMENT)
    assert txn.amount == Decimal("75.00")
    assert txn.account_id == account.pk


def test_correct_balance_view_rejects_unchanged_value(client):
    profile = ProfileFactory()
    account = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    client.force_login(profile.user)

    response = client.post(
        reverse("transactions:correct_balance", args=[account.pk]),
        {"new_balance": "100.00", "date": "2026-01-15", "note": ""},
    )

    assert response.status_code == 200
    assert "new_balance" in response.context["form"].errors
    assert Transaction.objects.filter(user=profile.user).count() == 0


def test_correct_balance_view_404s_for_another_users_account(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    account = AccountFactory(user=other_profile.user, currency=other_profile.base_currency)
    client.force_login(profile.user)

    response = client.post(
        reverse("transactions:correct_balance", args=[account.pk]),
        {"new_balance": "500.00", "date": "2026-01-15", "note": ""},
    )

    assert response.status_code == 404


def test_editing_an_adjustment_transaction_redirects_instead_of_rendering_form(client):
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
    client.force_login(profile.user)

    response = client.get(reverse("transactions:edit", args=[txn.pk]))

    assert response.status_code == 302
    assert response.url == reverse("transactions:detail", args=[txn.pk])
