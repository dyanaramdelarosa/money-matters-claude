from decimal import Decimal

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.accounts.models import Account, AccountType
from apps.budgets.models import BudgetDefinition, BudgetScope
from apps.categories.models import Category, CategoryKind
from apps.transactions.models import Transaction, TransactionType
from apps.users.models import Profile


class UserFactory(DjangoModelFactory):
    class Meta:
        model = "auth.User"

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "password-123")


class ProfileFactory(DjangoModelFactory):
    class Meta:
        model = Profile

    user = factory.SubFactory(UserFactory)
    base_currency = "USD"


class AccountFactory(DjangoModelFactory):
    class Meta:
        model = Account

    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Account {n}")
    type = AccountType.BANK
    currency = "USD"
    opening_balance = "0.00"


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category

    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Category {n}")
    kind = CategoryKind.EXPENSE


class TransactionFactory(DjangoModelFactory):
    class Meta:
        model = Transaction

    user = factory.SubFactory(UserFactory)
    type = TransactionType.EXPENSE
    amount = Decimal("10.00")
    currency = "USD"
    date = factory.LazyFunction(timezone.localdate)
    account = factory.SubFactory(AccountFactory, user=factory.SelfAttribute("..user"))
    category = factory.SubFactory(CategoryFactory, user=factory.SelfAttribute("..user"))


class BudgetDefinitionFactory(DjangoModelFactory):
    class Meta:
        model = BudgetDefinition

    user = factory.SubFactory(UserFactory)
    category = factory.SubFactory(CategoryFactory, user=factory.SelfAttribute("..user"))
    scope = BudgetScope.MONTHLY
    amount = Decimal("500.00")
