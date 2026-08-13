from django import forms

from apps.core.forms import UniqueActiveNameFormMixin

from .models import Account


class AccountCreateForm(UniqueActiveNameFormMixin, forms.ModelForm):
    name_conflict_message = "You already have an active account with this name."

    class Meta:
        model = Account
        fields = ["name", "type", "opening_balance"]


class AccountEditForm(UniqueActiveNameFormMixin, forms.ModelForm):
    name_conflict_message = "You already have an active account with this name."

    class Meta:
        model = Account
        fields = ["name", "type"]


class AccountOpeningBalanceForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ["opening_balance"]
