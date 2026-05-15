from ...core.errors import AeatError


class CurrencyError(AeatError):
    """Base exception for currency normalization."""


class MissingExchangeRateError(CurrencyError):
    """Raised when an exchange rate is missing for a given date/currency."""


class UnsupportedCurrencyError(CurrencyError):
    """Raised when an unknown currency code is encountered."""
