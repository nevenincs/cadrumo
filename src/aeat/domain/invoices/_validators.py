"""Counterparty identity validators for invoice records.

The EU-IVA prefix check and ISO-3166 alpha-2 country-code normaliser
remain in this module because they are invoice-domain concerns.
Each helper raises :class:`ValueError` on failure so pydantic
surfaces the error as a validation error in the enclosing
``Invoice`` model.

The registry-grounded helpers
:func:`is_eu_member_state_code` and :func:`assert_eu_member_state_code`
anchor the EU axis to the substrate's :class:`aeat.domain.iva.EUMemberState`
enum. Modelo 369 binding selectors and the OSS / IOSS classifier
boundary checks consume these helpers so the EU membership decision
flows from the substrate, not from a hand-maintained list.
"""

from __future__ import annotations

import re

from ..iva import EUMemberState
from ._errors import InvoiceValidationError

__all__ = [
    "EU_MEMBER_STATE_CODES",
    "assert_eu_member_state_code",
    "is_eu_member_state_code",
    "validate_country_code",
    "validate_iva_number",
]

_IVA_BODY_RE = re.compile(r"^[a-zA-Z0-9]{4,20}$")
_ISO_2_RE = re.compile(r"^[A-Z]{2}$")


EU_MEMBER_STATE_CODES: frozenset[str] = frozenset(member.value.upper() for member in EUMemberState)
"""Closed set of ISO-3166 alpha-2 codes (uppercase) for the 27 EU
Member States, sourced directly from :class:`aeat.domain.iva.EUMemberState`."""


def validate_country_code(value: str) -> str:
    """Normalise and validate an ISO-3166 alpha-2 country code.

    Args:
        value: Raw country code to validate.

    Returns:
        The uppercased two-letter country code.

    Raises:
        InvoiceValidationError: If the input is not exactly two alphabetic characters.
    """
    normalized = value.strip().upper()
    if not _ISO_2_RE.match(normalized):
        raise InvoiceValidationError("country code must be an ISO-3166 alpha-2 value")
    return normalized


def is_eu_member_state_code(value: str) -> bool:
    """Return ``True`` when ``value`` matches one of the 27 EU Member State codes.

    The membership check is anchored to
    :class:`aeat.domain.iva.EUMemberState`; if the substrate's enum
    changes (Brexit-style additions or withdrawals) the helper picks
    up the new shape automatically.

    Args:
        value: Raw country code to check.

    Returns:
        ``True`` when ``value`` normalises to one of the 27 EU codes.
    """
    try:
        normalized = validate_country_code(value)
    except InvoiceValidationError:
        return False
    return normalized in EU_MEMBER_STATE_CODES


def assert_eu_member_state_code(value: str) -> str:
    """Validate ``value`` and assert it names an EU Member State.

    Args:
        value: Raw country code to validate.

    Returns:
        The uppercased two-letter EU Member State code.

    Raises:
        InvoiceValidationError: If the input is malformed or names a non-EU country.
    """
    normalized = validate_country_code(value)
    if normalized not in EU_MEMBER_STATE_CODES:
        raise InvoiceValidationError(
            f"country code {normalized!r} is not one of the 27 EU Member States; "
            "use validate_country_code if a non-EU counterparty is acceptable",
        )
    return normalized


def validate_iva_number(value: str, country: str) -> str:
    """Validate a non-ES EU IVA number shape against its country prefix.

    Full per-country checksum validation is out of scope; the helper
    enforces only the leading ISO-2 country prefix plus a 4-20 character
    alphanumeric body.

    Args:
        value: Raw IVA identifier to validate.
        country: ISO-3166 alpha-2 country code already validated.

    Returns:
        The uppercased, whitespace-trimmed IVA identifier.

    Raises:
        InvoiceValidationError: If the value is malformed or the prefix does not match
            ``country``.
    """
    normalized = value.strip().upper().replace(" ", "").replace("-", "").replace(".", "")
    if not normalized:
        raise InvoiceValidationError("IVA number must not be blank")
    country_upper = country.strip().upper()
    if not normalized.startswith(country_upper):
        raise InvoiceValidationError("IVA number must start with the counterparty country ISO-2 prefix")
    body = normalized[len(country_upper) :]
    if not _IVA_BODY_RE.match(body):
        raise InvoiceValidationError("IVA number body must be 4-20 alphanumeric characters")
    return normalized
