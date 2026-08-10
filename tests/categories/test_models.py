import pytest
from django.db import IntegrityError

from apps.categories.models import Category, CategoryKind
from tests.factories import CategoryFactory

pytestmark = pytest.mark.django_db


def test_archive_sets_is_archived_and_archived_at():
    category = CategoryFactory()
    assert category.archived_at is None

    category.archive()

    assert category.is_archived is True
    assert category.archived_at is not None


def test_active_and_archived_querysets():
    active_category = CategoryFactory()
    archived_category = CategoryFactory()
    archived_category.archive()

    assert active_category in Category.objects.active()
    assert archived_category not in Category.objects.active()
    assert archived_category in Category.objects.archived()


def test_duplicate_category_name_for_same_user_is_rejected():
    category = CategoryFactory(name="Totally Custom Category")

    with pytest.raises(IntegrityError):
        Category.objects.create(
            user=category.user, name="Totally Custom Category", kind=CategoryKind.INCOME
        )


def test_archiving_a_category_frees_its_name_for_reuse():
    original = CategoryFactory(name="Totally Custom Category")
    original.archive()

    recreated = Category.objects.create(
        user=original.user, name="Totally Custom Category", kind=original.kind
    )

    assert recreated.pk != original.pk
    original.refresh_from_db()
    assert original.name == "Totally Custom Category"
