from django import forms
from django.utils import timezone

from apps.accounts.models import Account
from apps.categories.models import Category

from .models import Transaction, TransactionType


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = [
            "type",
            "date",
            "amount",
            "account",
            "transfer_to_account",
            "category",
            "note",
            "receipt_reference",
        ]

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        accounts = Account.objects.filter(user=user).active()
        self.fields["account"].queryset = accounts
        self.fields["transfer_to_account"].queryset = accounts
        self.fields["category"].queryset = Category.objects.filter(user=user).active()
        self.fields["date"].widget = forms.DateInput(attrs={"type": "date"})
        self.fields["type"].choices = [
            choice for choice in TransactionType.choices if choice[0] != TransactionType.ADJUSTMENT
        ]
        self.fields["type"].widget.attrs["x-model"] = "type"
        self.fields["transfer_to_account"].widget.attrs[":disabled"] = "type !== 'TRANSFER'"


class AccountBalanceCorrectionForm(forms.Form):
    new_balance = forms.DecimalField(max_digits=14, decimal_places=2, label="Correct balance to")
    date = forms.DateField(
        initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"})
    )
    note = forms.CharField(required=False, widget=forms.Textarea)

    def __init__(self, *args, account=None, **kwargs):
        self.account = account
        super().__init__(*args, **kwargs)

    def clean_new_balance(self):
        value = self.cleaned_data["new_balance"]
        if value == self.account.balance:
            raise forms.ValidationError("This is already the account's current balance.")
        return value


class TransactionFilterForm(forms.Form):
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    type = forms.ChoiceField(required=False, choices=[("", "All types")] + TransactionType.choices)
    account = forms.ModelChoiceField(
        required=False, queryset=Account.objects.none(), empty_label="All accounts"
    )
    category = forms.ModelChoiceField(
        required=False, queryset=Category.objects.none(), empty_label="All categories"
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = Account.objects.filter(user=user).active()
        self.fields["category"].queryset = Category.objects.filter(user=user).active()
