from django.db import transaction as db_transaction

from .models import Transaction


def _apply(effects):
    for account, delta in sorted(effects, key=lambda effect: effect[0].pk):
        account.adjust_balance(delta)


def create_transaction(instance):
    with db_transaction.atomic():
        instance.full_clean()
        instance.save()
        _apply(instance._effects())
    return instance


def update_transaction(instance):
    with db_transaction.atomic():
        old = Transaction.objects.select_for_update().get(pk=instance.pk)
        old_effects = old._effects()
        instance.full_clean()
        instance.save()
        _apply([(account, -delta) for account, delta in old_effects])
        _apply(instance._effects())
    return instance


def delete_transaction(instance):
    with db_transaction.atomic():
        locked = Transaction.objects.select_for_update().get(pk=instance.pk)
        effects = locked._effects()
        instance.delete()
        _apply([(account, -delta) for account, delta in effects])
