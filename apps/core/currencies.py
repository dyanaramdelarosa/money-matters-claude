"""Shared ISO-4217 currency data, reused by users.Profile and (from Milestone 3
onward) accounts/transactions. Hand-maintained subset of common currencies rather
than a dependency — extend as needed.
"""

CURRENCY_CHOICES = [
    ("USD", "US Dollar"),
    ("EUR", "Euro"),
    ("GBP", "British Pound"),
    ("JPY", "Japanese Yen"),
    ("AUD", "Australian Dollar"),
    ("CAD", "Canadian Dollar"),
    ("CHF", "Swiss Franc"),
    ("CNY", "Chinese Yuan"),
    ("HKD", "Hong Kong Dollar"),
    ("SGD", "Singapore Dollar"),
    ("NZD", "New Zealand Dollar"),
    ("INR", "Indian Rupee"),
    ("PHP", "Philippine Peso"),
    ("IDR", "Indonesian Rupiah"),
    ("MYR", "Malaysian Ringgit"),
    ("THB", "Thai Baht"),
    ("VND", "Vietnamese Dong"),
    ("KRW", "South Korean Won"),
    ("AED", "UAE Dirham"),
    ("SAR", "Saudi Riyal"),
    ("ZAR", "South African Rand"),
    ("BRL", "Brazilian Real"),
    ("MXN", "Mexican Peso"),
    ("SEK", "Swedish Krona"),
    ("NOK", "Norwegian Krone"),
    ("DKK", "Danish Krone"),
    ("PLN", "Polish Zloty"),
]

DEFAULT_CURRENCY = "USD"
