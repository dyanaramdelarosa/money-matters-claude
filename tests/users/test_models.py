import pytest

from apps.users.models import Profile

pytestmark = pytest.mark.django_db


def test_profile_links_to_its_user(django_user_model):
    user = django_user_model.objects.create_user(
        username="modeluser", email="model@example.com", password="password-123"
    )

    profile = Profile.objects.create(user=user, base_currency="EUR")

    assert user.profile == profile
    assert profile.user == user


def test_profile_str_includes_the_user(django_user_model):
    user = django_user_model.objects.create_user(
        username="struser", email="struser@example.com", password="password-123"
    )
    profile = Profile(user=user, base_currency="USD")

    assert str(profile) == f"Profile({user})"
