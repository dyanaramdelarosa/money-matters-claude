from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.models import Account, AccountType
from tests.factories import AccountFactory, ProfileFactory

pytestmark = pytest.mark.django_db


def test_list_view_requires_login(client):
    response = client.get(reverse("accounts:list"))

    assert response.status_code == 302
    assert reverse("account_login") in response.url


def test_list_view_only_shows_own_active_accounts(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    mine = AccountFactory(user=profile.user, currency=profile.base_currency)
    AccountFactory(user=other_profile.user, currency=other_profile.base_currency)
    archived = AccountFactory(user=profile.user, currency=profile.base_currency)
    archived.archive()

    client.force_login(profile.user)
    response = client.get(reverse("accounts:list"))

    assert list(response.context["accounts"]) == [mine]


def test_create_account_sets_user_and_currency_from_profile(client):
    profile = ProfileFactory(base_currency="PHP")
    client.force_login(profile.user)

    response = client.post(
        reverse("accounts:create"),
        {"name": "Savings", "type": AccountType.BANK, "opening_balance": "500.00"},
    )

    assert response.status_code == 302
    account = Account.objects.get(user=profile.user, name="Savings")
    assert account.currency == "PHP"
    assert account.balance == Decimal("500.00")


def test_create_account_with_duplicate_active_name_shows_form_error(client):
    profile = ProfileFactory()
    AccountFactory(user=profile.user, currency=profile.base_currency, name="Wallet")
    client.force_login(profile.user)

    response = client.post(
        reverse("accounts:create"),
        {"name": "Wallet", "type": AccountType.CASH, "opening_balance": "0.00"},
    )

    assert response.status_code == 200
    assert "name" in response.context["form"].errors
    assert Account.objects.filter(user=profile.user, name="Wallet").count() == 1


def test_create_account_reusing_archived_name_succeeds(client):
    profile = ProfileFactory()
    archived = AccountFactory(user=profile.user, currency=profile.base_currency, name="Wallet")
    archived.archive()
    client.force_login(profile.user)

    response = client.post(
        reverse("accounts:create"),
        {"name": "Wallet", "type": AccountType.CASH, "opening_balance": "0.00"},
    )

    assert response.status_code == 302
    assert Account.objects.filter(user=profile.user, name="Wallet").count() == 2


def test_detail_view_404s_for_another_users_account(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    account = AccountFactory(user=other_profile.user, currency=other_profile.base_currency)

    client.force_login(profile.user)
    response = client.get(reverse("accounts:detail", args=[account.pk]))

    assert response.status_code == 404


def test_edit_view_updates_name_and_type_but_not_opening_balance(client):
    profile = ProfileFactory()
    account = AccountFactory(
        user=profile.user,
        currency=profile.base_currency,
        opening_balance=Decimal("10.00"),
    )
    client.force_login(profile.user)

    response = client.post(
        reverse("accounts:edit", args=[account.pk]),
        {"name": "Renamed", "type": AccountType.CASH},
    )

    assert response.status_code == 302
    account.refresh_from_db()
    assert account.name == "Renamed"
    assert account.type == AccountType.CASH
    assert account.opening_balance == Decimal("10.00")


def test_edit_view_renaming_to_another_active_accounts_name_shows_form_error(client):
    profile = ProfileFactory()
    AccountFactory(user=profile.user, currency=profile.base_currency, name="Wallet")
    account = AccountFactory(user=profile.user, currency=profile.base_currency, name="Savings")
    client.force_login(profile.user)

    response = client.post(
        reverse("accounts:edit", args=[account.pk]),
        {"name": "Wallet", "type": account.type},
    )

    assert response.status_code == 200
    assert "name" in response.context["form"].errors
    account.refresh_from_db()
    assert account.name == "Savings"


def test_edit_view_404s_for_another_users_account(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    account = AccountFactory(user=other_profile.user, currency=other_profile.base_currency)

    client.force_login(profile.user)
    response = client.post(
        reverse("accounts:edit", args=[account.pk]),
        {"name": "Hijacked", "type": AccountType.CASH},
    )

    assert response.status_code == 404
    account.refresh_from_db()
    assert account.name != "Hijacked"


def test_opening_balance_view_updates_opening_balance_and_shifts_current_balance(client):
    profile = ProfileFactory()
    account = AccountFactory(
        user=profile.user, currency=profile.base_currency, opening_balance=Decimal("100.00")
    )
    account.adjust_balance(Decimal("-30.00"))
    account.refresh_from_db()
    assert account.balance == Decimal("70.00")
    client.force_login(profile.user)

    response = client.post(
        reverse("accounts:edit_opening_balance", args=[account.pk]),
        {"opening_balance": "150.00"},
    )

    assert response.status_code == 302
    account.refresh_from_db()
    assert account.opening_balance == Decimal("150.00")
    assert account.balance == Decimal("120.00")


def test_opening_balance_view_404s_for_another_users_account(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    account = AccountFactory(user=other_profile.user, currency=other_profile.base_currency)
    client.force_login(profile.user)

    response = client.post(
        reverse("accounts:edit_opening_balance", args=[account.pk]),
        {"opening_balance": "999.00"},
    )

    assert response.status_code == 404
    account.refresh_from_db()
    assert account.opening_balance != Decimal("999.00")


def test_archive_view_archives_own_account(client):
    profile = ProfileFactory()
    account = AccountFactory(user=profile.user, currency=profile.base_currency)
    client.force_login(profile.user)

    response = client.post(reverse("accounts:archive", args=[account.pk]))

    assert response.status_code == 302
    account.refresh_from_db()
    assert account.is_archived is True


def test_archive_view_404s_for_another_users_account(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    account = AccountFactory(user=other_profile.user, currency=other_profile.base_currency)

    client.force_login(profile.user)
    response = client.post(reverse("accounts:archive", args=[account.pk]))

    assert response.status_code == 404
    account.refresh_from_db()
    assert account.is_archived is False
