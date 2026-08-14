from decimal import Decimal

import pytest
from django.urls import reverse
from freezegun import freeze_time

from apps.budgets.models import BudgetDefinition, BudgetScope
from apps.budgets.services import get_or_create_period, spent_for_period
from apps.categories.models import CategoryKind
from tests.factories import BudgetDefinitionFactory, CategoryFactory, ProfileFactory

pytestmark = pytest.mark.django_db


def test_list_view_requires_login(client):
    response = client.get(reverse("budgets:list"))

    assert response.status_code == 302
    assert reverse("account_login") in response.url


def test_list_view_only_shows_own_active_budgets(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    mine = BudgetDefinitionFactory(user=profile.user)
    BudgetDefinitionFactory(user=other_profile.user)
    archived = BudgetDefinitionFactory(user=profile.user)
    archived.archive()

    client.force_login(profile.user)
    response = client.get(reverse("budgets:list"))

    assert list(response.context["budgets"]) == [mine]


def test_list_view_shows_spent_and_remaining_matching_the_service(client):
    profile = ProfileFactory()
    definition = BudgetDefinitionFactory(user=profile.user, amount=Decimal("500"))
    client.force_login(profile.user)

    response = client.get(reverse("budgets:list"))

    period = get_or_create_period(definition)
    spent = spent_for_period(period)
    row = response.context["rows"][0]
    assert row["spent"] == spent
    assert row["remaining"] == period.amount - spent


def test_create_budget_sets_user(client):
    profile = ProfileFactory()
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    client.force_login(profile.user)

    response = client.post(
        reverse("budgets:create"),
        {"category": category.pk, "scope": BudgetScope.MONTHLY, "amount": "300.00"},
    )

    assert response.status_code == 302
    definition = BudgetDefinition.objects.get(user=profile.user, category=category)
    assert definition.amount == Decimal("300.00")


def test_create_overall_budget_leaves_category_blank(client):
    profile = ProfileFactory()
    client.force_login(profile.user)

    response = client.post(
        reverse("budgets:create"),
        {"category": "", "scope": BudgetScope.MONTHLY, "amount": "1000.00"},
    )

    assert response.status_code == 302
    definition = BudgetDefinition.objects.get(user=profile.user, category=None)
    assert definition.amount == Decimal("1000.00")


def test_create_duplicate_active_category_and_scope_shows_form_error(client):
    profile = ProfileFactory()
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    BudgetDefinitionFactory(user=profile.user, category=category, scope=BudgetScope.MONTHLY)
    client.force_login(profile.user)

    response = client.post(
        reverse("budgets:create"),
        {"category": category.pk, "scope": BudgetScope.MONTHLY, "amount": "100.00"},
    )

    assert response.status_code == 200
    assert response.context["form"].errors
    assert BudgetDefinition.objects.filter(user=profile.user, category=category).count() == 1


def test_edit_budget_amount_updates_current_period(client):
    profile = ProfileFactory()
    definition = BudgetDefinitionFactory(
        user=profile.user, scope=BudgetScope.MONTHLY, amount=Decimal("500")
    )
    client.force_login(profile.user)

    with freeze_time("2026-06-10"):
        get_or_create_period(definition)
        response = client.post(
            reverse("budgets:edit", kwargs={"pk": definition.pk}), {"amount": "750.00"}
        )
        assert response.status_code == 302

        definition.refresh_from_db()
        assert definition.amount == Decimal("750.00")
        period = get_or_create_period(definition)
        assert period.amount == Decimal("750.00")


def test_edit_budget_cross_user_404(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    other_definition = BudgetDefinitionFactory(user=other_profile.user)
    client.force_login(profile.user)

    response = client.post(
        reverse("budgets:edit", kwargs={"pk": other_definition.pk}), {"amount": "1.00"}
    )

    assert response.status_code == 404


def test_archive_budget(client):
    profile = ProfileFactory()
    definition = BudgetDefinitionFactory(user=profile.user)
    client.force_login(profile.user)

    response = client.post(reverse("budgets:archive", kwargs={"pk": definition.pk}))

    assert response.status_code == 302
    definition.refresh_from_db()
    assert definition.is_archived is True


def test_archive_budget_cross_user_404(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    other_definition = BudgetDefinitionFactory(user=other_profile.user)
    client.force_login(profile.user)

    response = client.post(reverse("budgets:archive", kwargs={"pk": other_definition.pk}))

    assert response.status_code == 404
