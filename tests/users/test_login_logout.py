import pytest
from django.urls import reverse

from apps.users.models import Profile

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(django_user_model):
    user = django_user_model.objects.create_user(
        username="loginuser", email="login@example.com", password="correct-password-123"
    )
    Profile.objects.create(user=user, base_currency="USD")
    return user


def test_login_with_correct_credentials_succeeds(client, user):
    response = client.post(
        reverse("account_login"),
        {"login": "login@example.com", "password": "correct-password-123"},
    )

    assert response.status_code == 302
    response = client.get(reverse("users:profile"))
    assert response.status_code == 200


def test_login_with_wrong_password_fails(client, user):
    response = client.post(
        reverse("account_login"),
        {"login": "login@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 200
    assert not response.wsgi_request.user.is_authenticated


def test_logout_ends_the_session(client, user):
    client.force_login(user)

    response = client.post(reverse("account_logout"))

    assert response.status_code == 302
    response = client.get(reverse("users:profile"))
    assert response.status_code == 302
