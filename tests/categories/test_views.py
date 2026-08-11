import pytest
from django.urls import reverse

from apps.categories.models import Category, CategoryKind
from tests.factories import CategoryFactory, ProfileFactory

pytestmark = pytest.mark.django_db


def test_list_view_requires_login(client):
    response = client.get(reverse("categories:list"))

    assert response.status_code == 302
    assert reverse("account_login") in response.url


def test_list_view_only_shows_own_active_categories(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    mine = CategoryFactory(user=profile.user, name="Custom Category")
    CategoryFactory(user=other_profile.user, name="Not Mine")
    archived = CategoryFactory(user=profile.user, name="Archived Category")
    archived.archive()

    client.force_login(profile.user)
    response = client.get(reverse("categories:list"))

    names = {c.name for c in response.context["categories"]}
    assert mine.name in names
    assert "Not Mine" not in names
    assert "Archived Category" not in names


def test_create_category_sets_user(client):
    profile = ProfileFactory()
    client.force_login(profile.user)

    response = client.post(
        reverse("categories:create"), {"name": "Side Hustle", "kind": CategoryKind.INCOME}
    )

    assert response.status_code == 302
    assert Category.objects.get(user=profile.user, name="Side Hustle").kind == CategoryKind.INCOME


def test_create_category_with_duplicate_active_name_shows_form_error(client):
    profile = ProfileFactory()
    CategoryFactory(user=profile.user, name="Side Hustle")
    client.force_login(profile.user)

    response = client.post(
        reverse("categories:create"), {"name": "Side Hustle", "kind": CategoryKind.INCOME}
    )

    assert response.status_code == 200
    assert "name" in response.context["form"].errors
    assert Category.objects.filter(user=profile.user, name="Side Hustle").count() == 1


def test_create_category_reusing_archived_name_succeeds(client):
    profile = ProfileFactory()
    archived = CategoryFactory(user=profile.user, name="Side Hustle")
    archived.archive()
    client.force_login(profile.user)

    response = client.post(
        reverse("categories:create"), {"name": "Side Hustle", "kind": CategoryKind.INCOME}
    )

    assert response.status_code == 302
    assert Category.objects.filter(user=profile.user, name="Side Hustle").count() == 2


def test_edit_view_renaming_to_another_active_categorys_name_shows_form_error(client):
    profile = ProfileFactory()
    CategoryFactory(user=profile.user, name="Groceries2")
    category = CategoryFactory(user=profile.user, name="Savings Goal")
    client.force_login(profile.user)

    response = client.post(
        reverse("categories:edit", args=[category.pk]),
        {"name": "Groceries2", "kind": category.kind},
    )

    assert response.status_code == 200
    assert "name" in response.context["form"].errors
    category.refresh_from_db()
    assert category.name == "Savings Goal"


def test_edit_view_404s_for_another_users_category(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    category = CategoryFactory(user=other_profile.user)

    client.force_login(profile.user)
    response = client.post(
        reverse("categories:edit", args=[category.pk]),
        {"name": "Hijacked", "kind": category.kind},
    )

    assert response.status_code == 404
    category.refresh_from_db()
    assert category.name != "Hijacked"


def test_archive_view_archives_own_category(client):
    profile = ProfileFactory()
    category = CategoryFactory(user=profile.user)
    client.force_login(profile.user)

    response = client.post(reverse("categories:archive", args=[category.pk]))

    assert response.status_code == 302
    category.refresh_from_db()
    assert category.is_archived is True


def test_archive_view_404s_for_another_users_category(client):
    profile = ProfileFactory()
    other_profile = ProfileFactory()
    category = CategoryFactory(user=other_profile.user)

    client.force_login(profile.user)
    response = client.post(reverse("categories:archive", args=[category.pk]))

    assert response.status_code == 404
    category.refresh_from_db()
    assert category.is_archived is False
