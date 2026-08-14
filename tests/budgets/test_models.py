from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.budgets.models import BudgetDefinition, BudgetScope
from apps.categories.models import CategoryKind
from tests.factories import BudgetDefinitionFactory, CategoryFactory, ProfileFactory

pytestmark = pytest.mark.django_db


def test_duplicate_active_budget_for_same_category_and_scope_is_rejected():
    profile = ProfileFactory()
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)
    BudgetDefinitionFactory(
        user=profile.user, category=category, scope=BudgetScope.MONTHLY, amount=Decimal("500")
    )

    with pytest.raises(IntegrityError):
        BudgetDefinition.objects.create(
            user=profile.user,
            category=category,
            scope=BudgetScope.MONTHLY,
            amount=Decimal("100"),
        )


def test_archiving_frees_the_category_and_scope_for_reuse():
    definition = BudgetDefinitionFactory()
    definition.archive()

    recreated = BudgetDefinition.objects.create(
        user=definition.user,
        category=definition.category,
        scope=definition.scope,
        amount=Decimal("999"),
    )

    assert recreated.pk != definition.pk


def test_duplicate_active_overall_budget_for_same_scope_is_rejected():
    profile = ProfileFactory()
    BudgetDefinition.objects.create(
        user=profile.user, category=None, scope=BudgetScope.MONTHLY, amount=Decimal("1000")
    )

    with pytest.raises(IntegrityError):
        BudgetDefinition.objects.create(
            user=profile.user, category=None, scope=BudgetScope.MONTHLY, amount=Decimal("200")
        )


def test_overall_and_category_budgets_can_coexist_for_same_scope():
    profile = ProfileFactory()
    category = CategoryFactory(user=profile.user, kind=CategoryKind.EXPENSE)

    overall = BudgetDefinition.objects.create(
        user=profile.user, category=None, scope=BudgetScope.MONTHLY, amount=Decimal("1000")
    )
    per_category = BudgetDefinition.objects.create(
        user=profile.user, category=category, scope=BudgetScope.MONTHLY, amount=Decimal("200")
    )

    assert overall.pk != per_category.pk


def test_clean_rejects_category_belonging_to_another_user():
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    other_category = CategoryFactory(user=other_profile.user, kind=CategoryKind.EXPENSE)
    definition = BudgetDefinition(
        user=profile.user, category=other_category, scope=BudgetScope.MONTHLY, amount=Decimal("1")
    )

    with pytest.raises(ValidationError):
        definition.clean()


def test_clean_rejects_income_kind_category():
    profile = ProfileFactory()
    income_category = CategoryFactory(user=profile.user, kind=CategoryKind.INCOME)
    definition = BudgetDefinition(
        user=profile.user,
        category=income_category,
        scope=BudgetScope.MONTHLY,
        amount=Decimal("1"),
    )

    with pytest.raises(ValidationError):
        definition.clean()


def test_archive_sets_is_archived_and_archived_at():
    definition = BudgetDefinitionFactory()
    assert definition.archived_at is None

    definition.archive()

    assert definition.is_archived is True
    assert definition.archived_at is not None
