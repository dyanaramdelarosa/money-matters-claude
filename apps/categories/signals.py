from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .defaults import DEFAULT_EXPENSE_CATEGORIES, DEFAULT_INCOME_CATEGORIES
from .models import Category, CategoryKind


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def seed_default_categories(sender, instance, created, **kwargs):
    if not created:
        return

    Category.objects.bulk_create(
        [
            Category(user=instance, name=name, kind=CategoryKind.EXPENSE)
            for name in DEFAULT_EXPENSE_CATEGORIES
        ]
        + [
            Category(user=instance, name=name, kind=CategoryKind.INCOME)
            for name in DEFAULT_INCOME_CATEGORIES
        ]
    )
