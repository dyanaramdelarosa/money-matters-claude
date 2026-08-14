from decimal import Decimal, InvalidOperation

from django import template

from apps.core.currencies import CURRENCY_SYMBOLS

register = template.Library()


@register.filter
def money(value, currency_code=None):
    """Formats a numeric amount at a fixed 2 decimal places with thousands
    separators, prefixed with the currency's display symbol (falling back to
    the raw ISO code if it isn't in CURRENCY_SYMBOLS). Negative values keep
    the sign in front of the symbol (e.g. "-$1,050.00"), not between it and
    the digits.
    """
    if value in (None, ""):
        return ""
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return value
    symbol = CURRENCY_SYMBOLS.get(currency_code, f"{currency_code} " if currency_code else "")
    sign = "-" if amount < 0 else ""
    return f"{sign}{symbol}{abs(amount):,.2f}"
