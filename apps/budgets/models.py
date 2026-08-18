from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.categories.models import Category, CategoryKind
from apps.core.models import TimeStampedModel


class BudgetScope(models.TextChoices):
    SEMI_MONTHLY = "SEMI_MONTHLY", "Semi-monthly"
    MONTHLY = "MONTHLY", "Monthly"
    ANNUAL = "ANNUAL", "Annual"


class BudgetDefinitionQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_archived=False)

    def archived(self):
        return self.filter(is_archived=True)


class BudgetDefinition(TimeStampedModel):
    """The recurring budget rule a user sets up. The amount actually in force
    for a given period is snapshotted onto a BudgetPeriod the first time that
    period is needed — see apps.budgets.services — so editing this amount
    never retroactively changes an already-closed period's report.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="budget_definitions"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="budget_definitions",
        null=True,
        blank=True,
        help_text="Leave blank for an Overall budget spanning all expense categories.",
    )
    scope = models.CharField(max_length=20, choices=BudgetScope.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    second_half_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Semi-monthly only: a different amount for the 16th-end-of-month "
            "half. Leave blank to use the same amount as the first half."
        ),
    )
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)

    objects = BudgetDefinitionQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "category", "scope"],
                condition=Q(is_archived=False, category__isnull=False),
                name="unique_active_budget_per_user_category_scope",
            ),
            models.UniqueConstraint(
                fields=["user", "scope"],
                condition=Q(is_archived=False, category__isnull=True),
                name="unique_active_overall_budget_per_user_scope",
            ),
        ]
        ordering = ["scope", "category__name"]

    def __str__(self):
        target = self.category.name if self.category_id else "Overall"
        return f"{target} ({self.get_scope_display()})"

    def clean(self):
        if self.category_id and self.user_id and self.category.user_id != self.user_id:
            raise ValidationError({"category": "Category must belong to you."})
        if self.category_id and self.category.kind != CategoryKind.EXPENSE:
            raise ValidationError({"category": "Budgets can only be set on expense categories."})
        if self.second_half_amount is not None and self.scope != BudgetScope.SEMI_MONTHLY:
            raise ValidationError(
                {
                    "second_half_amount": (
                        "Only a semi-monthly budget can have a separate second-half amount."
                    )
                }
            )

    def archive(self):
        self.is_archived = True
        self.archived_at = timezone.now()
        self.save(update_fields=["is_archived", "archived_at", "updated_at"])


class BudgetPeriod(TimeStampedModel):
    """The materialized amount actually in force for one period instance of a
    BudgetDefinition — created lazily (apps.budgets.services.get_or_create_period)
    the first time that period is needed, snapshotting the definition's amount
    at that moment. Never user-submitted.
    """

    definition = models.ForeignKey(
        BudgetDefinition, on_delete=models.PROTECT, related_name="periods"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="budget_periods"
    )
    period_start = models.DateField()
    period_end = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["definition", "period_start"], name="unique_period_per_definition"
            )
        ]
        ordering = ["-period_start"]

    def __str__(self):
        return f"{self.definition} {self.period_start}–{self.period_end}"
