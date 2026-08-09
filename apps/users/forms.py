from allauth.account.forms import SignupForm as AllauthSignupForm
from django import forms

from apps.core.currencies import CURRENCY_CHOICES, DEFAULT_CURRENCY

from .models import Profile


class SignupForm(AllauthSignupForm):
    base_currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        initial=DEFAULT_CURRENCY,
        label="Base currency",
        help_text="All your accounts and transactions will use this currency.",
    )

    def save(self, request):
        user = super().save(request)
        Profile.objects.create(user=user, base_currency=self.cleaned_data["base_currency"])
        return user
