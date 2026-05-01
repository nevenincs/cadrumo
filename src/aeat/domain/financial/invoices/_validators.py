"""Counterparty identity validators for invoice records.

The Spanish tax-identity algorithm (:func:`validate_spanish_tax_id`)
moved to :mod:`aeat.adapters.inbound.identity` so other subpackages
(storage, sanitizer, CLI submission gates) can import it from a public
surface instead of reaching into this private module. The function is
re-exported here for invoice-side callers that bind to the name
locally.

The EU-VAT prefix check and ISO-3166 alpha-2 country-code normaliser
remain in this module because they are invoice-domain concerns.
Each helper raises :class:`ValueError` on failure so pydantic
surfaces the error as a validation error in the enclosing
``Invoice`` model.
"""

from __future__ import annotations

from ....adapters.inbound.identity import validate_spanish_tax_id

__all__ = ["validate_country_code", "validate_spanish_tax_id", "validate_vat_number"]


def validate_country_code(value: str) -> str:
    """Normalise and validate an ISO-3166 alpha-2 country code.

    Args:
        value: Raw country code to validate.

    Returns:
        The uppercased two-letter country code.

    Raises:
        ValueError: If the input is not exactly two alphabetic characters.
    """
    normalized = value.strip().upper()
    if len(normalized) != 2 or not normalized.isalpha():
        raise ValueError("country code must be an ISO-3166 alpha-2 value")
    return normalized


def validate_vat_number(value: str, country: str) -> str:
    """Validate a non-ES EU VAT number shape against its country prefix.

    Full per-country checksum validation is out of scope; the helper
    enforces only the leading ISO-2 country prefix plus a 4-20 character
    alphanumeric body.

    Args:
        value: Raw VAT identifier to validate.
        country: ISO-3166 alpha-2 country code already validated.

    Returns:
        The uppercased, whitespace-trimmed VAT identifier.

    Raises:
        ValueError: If the value is malformed or the prefix does not match
            ``country``.
    """
    normalized = value.strip().upper().replace(" ", "").replace("-", "").replace(".", "")
    if not normalized:
        raise ValueError("VAT number must not be blank")
    country_upper = country.strip().upper()
    if not normalized.startswith(country_upper):
        raise ValueError("VAT number must start with the counterparty country ISO-2 prefix")
    body = normalized[len(country_upper) :]
    if not (4 <= len(body) <= 20) or not body.isalnum():
        raise ValueError("VAT number body must be 4-20 alphanumeric characters")
    return normalized
