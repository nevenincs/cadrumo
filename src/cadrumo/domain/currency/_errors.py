"""Domain error hierarchy for currency normalization and exchange-rate lookup.

All exceptions extend :class:`~cadrumo.core.errors.CadrumoError` so callers can
catch either the domain-specific type or the project-wide base class.
"""

from ...core.errors import CadrumoError


class CurrencyError(CadrumoError):
    """Base exception for currency normalization."""


class MissingExchangeRateError(CurrencyError):
    """Raised when an exchange rate is missing for a given date/currency."""


class UnsupportedCurrencyError(CurrencyError):
    """Raised when an unknown currency code is encountered."""


class ExchangeRateProviderError(CurrencyError):
    """Raised when an upstream exchange-rate adapter fails to respond."""


class StaleExchangeRateError(CurrencyError):
    """Raised when the only available rate is outside the acceptable freshness window."""
