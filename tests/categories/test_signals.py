import pytest

from apps.categories.defaults import DEFAULT_EXPENSE_CATEGORIES, DEFAULT_INCOME_CATEGORIES
from apps.categories.models import Category, CategoryKind
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_new_user_gets_default_categories_seeded():
    user = UserFactory()

    categories = Category.objects.filter(user=user)

    assert categories.count() == len(DEFAULT_EXPENSE_CATEGORIES) + len(DEFAULT_INCOME_CATEGORIES)


def test_default_categories_have_correct_kinds():
    user = UserFactory()

    expense_names = set(
        Category.objects.filter(user=user, kind=CategoryKind.EXPENSE).values_list("name", flat=True)
    )
    income_names = set(
        Category.objects.filter(user=user, kind=CategoryKind.INCOME).values_list("name", flat=True)
    )

    assert expense_names == set(DEFAULT_EXPENSE_CATEGORIES)
    assert income_names == set(DEFAULT_INCOME_CATEGORIES)


def test_updating_an_existing_user_does_not_reseed_categories():
    user = UserFactory()
    initial_count = Category.objects.filter(user=user).count()

    user.first_name = "Changed"
    user.save()

    assert Category.objects.filter(user=user).count() == initial_count
