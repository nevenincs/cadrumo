"""Counterparty identity validators for invoice records.

The EU-IVA prefix check and ISO-3166 alpha-2 country-code normaliser
remain in this module because they are invoice-domain concerns.
Each helper raises :class:`ValueError` on failure so pydantic
surfaces the error as a validation error in the enclosing
``Invoice`` model.

The registry-grounded helpers
:func:`is_eu_member_state_code` and :func:`assert_eu_member_state_code`
anchor the EU axis to the substrate's :class:`cadrumo.domain.iva.EUMemberState`
enum. Modelo 369 binding selectors and the OSS / IOSS classifier
boundary checks consume these helpers so the EU membership decision
flows from the substrate, not from a hand-maintained list.
"""

from __future__ import annotations

import re

from ...core.country_code import COUNTRY_CODE_ALPHA2_PATTERN
from ...core.identity import nif_iva_format_for_country, normalise_nif_iva
from ..iva.schema import EUMemberState
from .errors import InvoiceValidationError

__all__ = [
    "EU_MEMBER_STATE_CODES",
    "assert_eu_member_state_code",
    "assert_non_domestic_country_code",
    "is_eu_member_state_code",
    "validate_country_code",
    "validate_iva_number",
]

_IVA_BODY_RE = re.compile(r"^[a-zA-Z0-9]{4,20}$")
_ISO_2_RE = re.compile(rf"^{COUNTRY_CODE_ALPHA2_PATTERN}$")


EU_MEMBER_STATE_CODES: frozenset[str] = frozenset(
    member.value.upper() for member in EUMemberState if member is not EUMemberState.XI
)
"""Closed set of ISO-3166 alpha-2 codes (uppercase) for the 27 EU
Member States, sourced from :class:`cadrumo.domain.iva.EUMemberState` while
excluding the Northern Ireland IVA prefix ``XI``."""


def validate_country_code(value: str) -> str:
    """Normalise and validate an ISO-3166 alpha-2 country code.

    Folds case, unlike
    :func:`~cadrumo.core.parsing.normalise_iso_3166_alpha2_jurisdiction`, which
    refuses a lowercase token so the regulatory treatment of a ledger row is
    never guessed. A counterparty's country is a label on an invoice rather than
    a treatment selector, so folding an operator's ``"es"`` here costs nothing.
    The two share :data:`~cadrumo.core.country_code.COUNTRY_CODE_ALPHA2_PATTERN`
    and nothing else.

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
    :class:`cadrumo.domain.iva.EUMemberState`; if the substrate's enum
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


def assert_non_domestic_country_code(value: str) -> str:
    """Validate ``value`` and assert it does not name Spain.

    An entrega intracomunitaria exenta (LIVA art. 25) is, by its own legal
    definition, a delivery TO another territory: Spain can never be its own
    destination. Deliberately narrower than requiring EU membership --
    Northern Ireland (``XI``) is a legitimate M349 goods destination under
    the Windsor Framework despite not being one of the 27 Member States
    :func:`assert_eu_member_state_code` recognises, and a non-EU destination
    (e.g. ``GB``) is a real declared fact this helper does not itself judge;
    downstream M349 classification decides which non-Spanish destinations
    are declarable, not this construction-time check.

    Args:
        value: Raw country code to validate.

    Returns:
        The uppercased two-letter country code.

    Raises:
        InvoiceValidationError: If the input is malformed or names Spain.
    """
    normalized = validate_country_code(value)
    if normalized == "ES":
        raise InvoiceValidationError(
            "an entrega intracomunitaria exenta must name a destination other than Spain "
            "(LIVA art. 25); Spain cannot be its own intra-community destination",
        )
    return normalized


def validate_iva_number(value: str, country: str) -> str:
    """Validate a non-ES IVA number shape against its country format.

    For an EU Member State (and Northern Ireland ``XI``) the number is matched
    against the country's published NIF-IVA structural pattern, sourced from the
    central :data:`cadrumo.core.identity.NIF_IVA_FORMATS` authority: a malformed
    intra-community IVA number is bounced by AEAT's Modelo 349 validator, so the
    refusal names the country and the expected format. Live VIES existence is not
    checked — only the structure. For a non-EU counterparty (no published
    pattern) the helper falls back to a generic leading-prefix plus 4-20
    character alphanumeric body check, so non-EU counterparties remain
    acceptable.

    Args:
        value: Raw IVA identifier to validate.
        country: ISO-3166 alpha-2 country code already validated.

    Returns:
        The uppercased, whitespace-trimmed IVA identifier.

    Raises:
        InvoiceValidationError: If the value is malformed, the prefix does not
            match ``country``, or the EU NIF-IVA format does not match.
    """
    normalized = normalise_nif_iva(value)
    if not normalized:
        raise InvoiceValidationError("IVA number must not be blank")

    spec = nif_iva_format_for_country(country)
    if spec is not None:
        if not spec.pattern.match(normalized):
            raise InvoiceValidationError(
                f"IVA number {normalized!r} is not a valid {spec.country_name} NIF-IVA: "
                f"expected {spec.description} (e.g. {spec.example})",
            )
        return normalized

    country_upper = country.strip().upper()
    if not normalized.startswith(country_upper):
        raise InvoiceValidationError("IVA number must start with the counterparty country ISO-2 prefix")
    body = normalized[len(country_upper) :]
    if not _IVA_BODY_RE.match(body):
        raise InvoiceValidationError("IVA number body must be 4-20 alphanumeric characters")
    return normalized
