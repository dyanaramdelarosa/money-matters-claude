from django import forms
from django.core.exceptions import ValidationError

from apps.categories.models import Category, CategoryKind

from .models import BudgetDefinition, BudgetScope


class BudgetDefinitionForm(forms.ModelForm):
    class Meta:
        model = BudgetDefinition
        fields = ["category", "scope", "amount", "second_half_amount"]
        labels = {"second_half_amount": "Second-half amount (optional)"}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["category"].queryset = Category.objects.filter(
            user=user, kind=CategoryKind.EXPENSE
        ).active()
        self.fields["category"].required = False
        self.fields["category"].empty_label = "Overall (all expenses)"
        self.fields["second_half_amount"].required = False

    def clean(self):
        cleaned_data = super().clean()
        scope = cleaned_data.get("scope")
        category = cleaned_data.get("category")
        if self.user and scope:
            conflicts = BudgetDefinition.objects.filter(
                user=self.user, scope=scope, category=category, is_archived=False
            )
            if self.instance.pk:
                conflicts = conflicts.exclude(pk=self.instance.pk)
            if conflicts.exists():
                target = category.name if category else "Overall"
                raise ValidationError(
                    f"You already have an active {target} budget for this period."
                )
        return cleaned_data


class BudgetAmountEditForm(forms.ModelForm):
    class Meta:
        model = BudgetDefinition
        fields = ["amount", "second_half_amount"]
        labels = {"second_half_amount": "Second-half amount (optional)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["second_half_amount"].required = False
        # Scope is fixed at creation — only a semi-monthly budget ever has a
        # second half to set an amount for, so the field is dropped entirely
        # (rather than just hidden) for every other scope.
        if self.instance.scope != BudgetScope.SEMI_MONTHLY:
            del self.fields["second_half_amount"]
