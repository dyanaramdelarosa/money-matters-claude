import pytest
from django.urls import reverse

from apps.users.models import Profile

pytestmark = pytest.mark.django_db


def _signup_data(**overrides):
    data = {
        "email": "new-user@example.com",
        "password1": "a-very-strong-password-123",
        "password2": "a-very-strong-password-123",
        "base_currency": "EUR",
    }
    data.update(overrides)
    return data


def test_signup_creates_a_profile_with_the_chosen_currency(client):
    response = client.post(reverse("account_signup"), _signup_data())

    assert response.status_code == 302
    profile = Profile.objects.get(user__email="new-user@example.com")
    assert profile.base_currency == "EUR"


def test_signup_logs_the_user_in_immediately(client):
    client.post(reverse("account_signup"), _signup_data())

    response = client.get(reverse("users:profile"))

    assert response.status_code == 200
    assert response.context["profile"].user.email == "new-user@example.com"


def test_signup_rejects_mismatched_passwords(client):
    response = client.post(reverse("account_signup"), _signup_data(password2="different"))

    assert response.status_code == 200
    assert not Profile.objects.filter(user__email="new-user@example.com").exists()
