from django.conf import settings
from django.db import models

from apps.core.currencies import CURRENCY_CHOICES, DEFAULT_CURRENCY
from apps.core.models import TimeStampedModel


class Profile(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    base_currency = models.CharField(
        max_length=3, choices=CURRENCY_CHOICES, default=DEFAULT_CURRENCY
    )

    def __str__(self):
        return f"Profile({self.user})"
