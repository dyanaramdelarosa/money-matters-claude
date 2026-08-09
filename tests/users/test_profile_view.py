import pytest
from django.urls import reverse

from apps.users.models import Profile

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(django_user_model):
    user = django_user_model.objects.create_user(
        username="profileuser", email="profile@example.com", password="password-123"
    )
    Profile.objects.create(user=user, base_currency="PHP")
    return user


def test_authenticated_user_sees_their_own_profile(client, user):
    client.force_login(user)

    response = client.get(reverse("users:profile"))

    assert response.status_code == 200
    assert response.context["profile"].user == user
    assert "PHP" in response.content.decode()


def test_anonymous_user_is_redirected_to_login(client):
    response = client.get(reverse("users:profile"))

    assert response.status_code == 302
    assert reverse("account_login") in response.url
