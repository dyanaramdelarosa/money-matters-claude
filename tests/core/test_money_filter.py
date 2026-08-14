from decimal import Decimal

from apps.core.templatetags.money import money


def test_formats_to_two_decimal_places_with_symbol():
    assert money(Decimal("500"), "USD") == "$500.00"
    assert money(Decimal("500.5"), "USD") == "$500.50"


def test_negative_amount_keeps_sign_in_front_of_symbol():
    assert money(Decimal("-50"), "USD") == "-$50.00"


def test_thousands_get_comma_separators():
    assert money(Decimal("1000"), "USD") == "$1,000.00"
    assert money(Decimal("1234567.5"), "USD") == "$1,234,567.50"


def test_negative_thousands_keep_sign_in_front_of_symbol():
    assert money(Decimal("-1000"), "USD") == "-$1,000.00"


def test_unmapped_currency_code_falls_back_to_the_code_itself():
    assert money(Decimal("10"), "XXX") == "XXX 10.00"


def test_no_currency_code_still_formats_two_decimal_places():
    assert money(Decimal("10")) == "10.00"


def test_blank_value_renders_empty():
    assert money(None, "USD") == ""
    assert money("", "USD") == ""
