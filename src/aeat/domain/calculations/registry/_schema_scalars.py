"""Scalar and annotated value types for registry schema models."""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Annotated

from pydantic import BeforeValidator, Field

from ....core import StandardPeriodCode
from ....core.decimal import coerce_decimal
from ....core.identity import IdentityError, validate_spanish_tax_id
from ._errors import RegistryValidationError

__all__ = [
    "BicString",
    "BindingSelectorMap",
    "BindingSelectorValue",
    "CCAACode",
    "CalendarDate",
    "CountryCode",
    "DecimalValue",
    "IbanString",
    "ModeloYear",
    "MunicipalityCode",
    "NifIvaString",
    "NifString",
    "PeriodCode",
    "PersonOrEntityName",
    "PostalCode",
    "ProvinceCode",
    "WorkbookCellRefStr",
    "_coerce_modelo_year",
    "_validate_country_code",
    "_validate_iban_string",
    "_validate_nif_string",
    "_validate_period_code",
]


def _coerce_decimal(value: object) -> object:
    if isinstance(value, bool | float):
        raise RegistryValidationError("decimal values must not be booleans or floats")
    if isinstance(value, Decimal):
        return value
    result = coerce_decimal(value)
    return result if result is not None else value


DecimalValue = Annotated[Decimal, BeforeValidator(_coerce_decimal)]


def _validate_nif_string(value: object) -> object:
    """Validate a Spanish NIF / NIE / CIF identifier and return its canonical form.

    Delegates to the shared `validate_spanish_tax_id` algorithm in
    `aeat.core.identity._tax_id` and re-raises domain `IdentityError`
    as `RegistryValidationError` so the schema boundary surfaces
    identifier-format problems through its established error type.
    """
    if not isinstance(value, str):
        raise RegistryValidationError(f"NIF value must be a string, got {type(value).__name__}")
    try:
        return validate_spanish_tax_id(value)
    except IdentityError as exc:
        raise RegistryValidationError(f"invalid NIF / NIE / CIF identifier: {exc}") from exc


NifString = Annotated[str, BeforeValidator(_validate_nif_string)]
"""Canonical Spanish tax-identifier string.

Used as the value type for casillas declaring `data_type = "nif"`,
and by any cross-domain consumer (filing draft assembly, oracle
replay, export layouts) that needs to validate a NIF, NIE, or CIF
identifier independently of a casilla declaration.
"""


def _coerce_modelo_year(value: object) -> object:
    """Coerce a fiscal-year input to an int within the registry-supported window.

    Accepts an int directly or a non-empty string of digits. Rejects
    booleans (which are int subclasses in Python), floats, and any
    value outside ``RegistrySnapshotRef.modelo_year``'s declared
    ``ge=2000, le=2099`` range.
    """
    if isinstance(value, bool):
        raise RegistryValidationError("year value must not be a boolean")
    if isinstance(value, float):
        raise RegistryValidationError("year value must not be a float")
    if isinstance(value, str):
        if not value.strip():
            raise RegistryValidationError("year value must not be blank")
        try:
            value = int(value)
        except ValueError as exc:
            raise RegistryValidationError(f"year value {value!r} is not a valid integer") from exc
    return value


ModeloYear = Annotated[int, BeforeValidator(_coerce_modelo_year), Field(ge=2000, le=2099)]
"""Canonical fiscal-year integer for the registry boundary.

Mirrors the ``RegistrySnapshotRef.modelo_year`` bound so a casilla
declaring ``data_type = "year"`` and the snapshot coordinate agree
on the supported window. Consumers that need to validate a year
value independently of a casilla declaration should type their
field as ``ModeloYear``.
"""


_STANDARD_PERIOD_CODES = frozenset(StandardPeriodCode)
_EXT_PATTERN = re.compile(r"^EXT-[1-4]T$")
_AD_HOC_PATTERN = re.compile(r"^AD-HOC$")
_EVENT_PATTERN = re.compile(r"^EVENT-\d+$")


def _validate_period_code(value: object) -> object:
    """Validate a filing-period code against the registry-supported set.

    Accepted forms (from the fiscal-period inventory):

    - StandardPeriodCode: 1T-4T (quarterly), 1P-4P (instalment), 0A (annual), 01-12 (monthly).
    - ``EXT-1T``-``EXT-4T``: OSS extra-Union scheme quarters (modelo 369).
    - ``AD-HOC``: ad-hoc / event-driven (modelos 308, 309).
    - ``EVENT-N``: numbered event filings.

    Modellers introducing a new form must extend this validator.
    """
    if not isinstance(value, str):
        raise RegistryValidationError(f"period_code value must be a string, got {type(value).__name__}")
    if value in _STANDARD_PERIOD_CODES:
        return value
    if _EXT_PATTERN.match(value) or _AD_HOC_PATTERN.match(value) or _EVENT_PATTERN.match(value):
        return value
    raise RegistryValidationError(f"period_code value {value!r} does not match a supported filing-period form")


PeriodCode = Annotated[str, BeforeValidator(_validate_period_code)]
"""Canonical filing-period code for the registry boundary.

Used as the value type for casillas declaring
``data_type = "period_code"``, and by any cross-domain consumer
(snapshot coordinates, oracle replay, export layouts) that needs to
validate a period token independently of a casilla declaration.
"""


_COUNTRY_CODE_RE = re.compile(r"^[A-Z]{2}$")


def _validate_country_code(value: object) -> object:
    """Validate a two-character ISO 3166-1 alpha-2 country code.

    Format-only validation: enforces uppercase ASCII letters and
    exact length 2. Membership against the AEAT-supported country
    list is delegated to per-casilla `constraints.enum` declarations
    (Plan B) and to the semantic-role consistency layer (Plan C).
    Country casillas declaring `data_type = "country_code"` are
    expected to either (a) carry an `enum` constraint enumerating
    the supported codes, or (b) accept any ISO alpha-2 code with
    downstream business validation.
    """
    if not isinstance(value, str):
        raise RegistryValidationError(f"country_code value must be a string, got {type(value).__name__}")
    if not _COUNTRY_CODE_RE.match(value):
        raise RegistryValidationError(
            f"country_code value {value!r} must be a two-character uppercase ISO alpha-2 code",
        )
    return value


CountryCode = Annotated[str, BeforeValidator(_validate_country_code)]
"""Two-character country code for the registry boundary.

Used as the value type for casillas declaring
``data_type = "country_code"``. Membership against the
AEAT-supported country list is layered through per-casilla `enum`
constraints (Plan B) and semantic-role consistency (Plan C); this
alias enforces only the alpha-2 shape.
"""


_IBAN_SHAPE_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")


def _iban_mod_97(canonical: str) -> int:
    """Compute the IBAN mod-97 check residue for an already-canonical IBAN."""
    rearranged = canonical[4:] + canonical[:4]
    numeric = "".join(ch if ch.isdigit() else str(ord(ch) - ord("A") + 10) for ch in rearranged)
    return int(numeric) % 97


def _validate_iban_string(value: object) -> object:
    """Validate an IBAN: country code, check digits, BBAN, and mod-97 residue.

    The validator strips whitespace and hyphens, uppercases, then
    enforces ISO 13616 shape (`CC kk BBAN`, total 15-34 chars) and
    the mod-97 check (the integer formed by moving the leading
    four chars to the tail and converting letters to digits must be
    congruent to 1 mod 97).
    """
    if not isinstance(value, str):
        raise RegistryValidationError(f"iban value must be a string, got {type(value).__name__}")
    canonical = value.replace(" ", "").replace("-", "").upper()
    if not canonical:
        raise RegistryValidationError("iban value must not be blank")
    if not _IBAN_SHAPE_RE.match(canonical):
        raise RegistryValidationError(f"iban value {value!r} does not match the ISO 13616 shape")
    if _iban_mod_97(canonical) != 1:
        raise RegistryValidationError(f"iban value {value!r} fails the mod-97 check")
    return canonical


IbanString = Annotated[str, BeforeValidator(_validate_iban_string)]
"""Canonical IBAN string for the registry boundary.

Used as the value type for casillas declaring ``data_type = "iban"``
and by any cross-domain consumer that needs to validate an IBAN
independently of a casilla declaration.
"""


def _validate_name_string(value: object) -> object:
    """Validate a personal or entity name: non-empty unicode within length bounds."""
    if not isinstance(value, str):
        raise RegistryValidationError(f"name value must be a string, got {type(value).__name__}")
    stripped = value.strip()
    if not stripped:
        raise RegistryValidationError("name value must not be blank")
    if len(stripped) > 200:
        raise RegistryValidationError(f"name value exceeds 200 characters: {len(stripped)}")
    return stripped


PersonOrEntityName = Annotated[str, BeforeValidator(_validate_name_string)]
"""Personal or entity name for the registry boundary."""


_NIF_IVA_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{2,12}$")


def _validate_nif_iva_string(value: object) -> object:
    """Validate an intracomunitario NIF-IVA: ISO country prefix plus identifier body."""
    if not isinstance(value, str):
        raise RegistryValidationError(f"nif_iva value must be a string, got {type(value).__name__}")
    canonical = value.replace(" ", "").replace("-", "").upper()
    if not _NIF_IVA_RE.match(canonical):
        raise RegistryValidationError(
            f"nif_iva value {value!r} must start with a two-letter country code "
            "followed by 2-12 alphanumeric characters",
        )
    return canonical


NifIvaString = Annotated[str, BeforeValidator(_validate_nif_iva_string)]
"""Intracomunitario NIF-IVA string for the registry boundary."""


_CCAA_CODES = frozenset(
    {
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
        "09",
        "10",
        "11",
        "12",
        "13",
        "14",
        "15",
        "16",
        "17",
        "18",
        "19",
    },
)


def _validate_ccaa_code(value: object) -> object:
    """Validate an autonomous-community code against the AEAT-supported set."""
    if not isinstance(value, str):
        raise RegistryValidationError(f"ccaa_code value must be a string, got {type(value).__name__}")
    if value not in _CCAA_CODES:
        raise RegistryValidationError(
            f"ccaa_code value {value!r} is not in the supported AEAT autonomous-community set",
        )
    return value


CCAACode = Annotated[str, BeforeValidator(_validate_ccaa_code)]
"""Autonomous-community code for the registry boundary."""


_PROVINCE_CODE_RE = re.compile(r"^(0[1-9]|[1-4][0-9]|5[0-2])$")


def _validate_province_code(value: object) -> object:
    """Validate a Spanish province code (01-52)."""
    if not isinstance(value, str):
        raise RegistryValidationError(f"province_code value must be a string, got {type(value).__name__}")
    if not _PROVINCE_CODE_RE.match(value):
        raise RegistryValidationError(
            f"province_code value {value!r} must be a two-digit Spanish province code (01-52)",
        )
    return value


ProvinceCode = Annotated[str, BeforeValidator(_validate_province_code)]
"""Two-digit Spanish province code for the registry boundary."""


_POSTAL_CODE_RE = re.compile(r"^\d{5}$")


def _validate_postal_code(value: object) -> object:
    """Validate a Spanish postal code (five digits)."""
    if not isinstance(value, str):
        raise RegistryValidationError(f"postal_code value must be a string, got {type(value).__name__}")
    if not _POSTAL_CODE_RE.match(value):
        raise RegistryValidationError(f"postal_code value {value!r} must be a five-digit Spanish postal code")
    return value


PostalCode = Annotated[str, BeforeValidator(_validate_postal_code)]
"""Five-digit Spanish postal code for the registry boundary."""


_MUNICIPALITY_CODE_RE = re.compile(r"^\d{5}$")


def _validate_municipality_code(value: object) -> object:
    """Validate a five-digit INE municipality code."""
    if not isinstance(value, str):
        raise RegistryValidationError(f"municipality_code value must be a string, got {type(value).__name__}")
    if not _MUNICIPALITY_CODE_RE.match(value):
        raise RegistryValidationError(f"municipality_code value {value!r} must be a five-digit INE municipality code")
    return value


MunicipalityCode = Annotated[str, BeforeValidator(_validate_municipality_code)]
"""Five-digit INE municipality code for the registry boundary."""


_BIC_RE = re.compile(r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$")


def _validate_bic_string(value: object) -> object:
    """Validate a SWIFT BIC (ISO 9362): 8 or 11 characters."""
    if not isinstance(value, str):
        raise RegistryValidationError(f"bic value must be a string, got {type(value).__name__}")
    canonical = value.replace(" ", "").upper()
    if not _BIC_RE.match(canonical):
        raise RegistryValidationError(f"bic value {value!r} must be 8 or 11 alphanumeric characters per ISO 9362")
    return canonical


BicString = Annotated[str, BeforeValidator(_validate_bic_string)]
"""SWIFT BIC for the registry boundary."""


_DATE_DDMMAAAA_RE = re.compile(r"^(0[1-9]|[12]\d|3[01])(0[1-9]|1[0-2])\d{4}$")
_DATE_ISO_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


def _validate_calendar_date(value: object) -> object:
    """Validate a calendar date in either ISO 8601 or AEAT `ddmmaaaa` form."""
    if not isinstance(value, str):
        raise RegistryValidationError(f"date value must be a string, got {type(value).__name__}")
    if not (_DATE_ISO_RE.match(value) or _DATE_DDMMAAAA_RE.match(value)):
        raise RegistryValidationError(f"date value {value!r} must be ISO 8601 (yyyy-mm-dd) or AEAT ddmmaaaa")
    return value


CalendarDate = Annotated[str, BeforeValidator(_validate_calendar_date)]
"""Calendar date string in ISO 8601 or AEAT `ddmmaaaa` form."""

_WORKBOOK_CELL_REF_RE = re.compile(r"^(?:(?P<sheet>'[^']+'|[^!]+)!)?(?P<coordinate>\$?[A-Z]{1,3}\$?\d+)$")


def _validate_workbook_cell_ref_str(value: object) -> object:
    if isinstance(value, str) and not _WORKBOOK_CELL_REF_RE.match(value):
        raise RegistryValidationError(f"invalid workbook cell reference {value!r}")
    return value


WorkbookCellRefStr = Annotated[str, BeforeValidator(_validate_workbook_cell_ref_str)]


BindingSelectorValue = str | int | DecimalValue | bool | tuple[str, ...]
"""Closed union of the value shapes a binding-selector entry can hold.

The selector field on :class:`DataBindingDefinition` and related
selector fields on relation definitions store this union. Per-source
typed selector models (declared in :mod:`_bindings`) consume the
raw mapping and re-validate against a strict frozen schema for the
binding's declared ``source``; the snapshot-time
``_validate_binding_selector_shapes`` gate runs that check on every
binding once at snapshot build.
"""

BindingSelectorMap = Mapping[str, BindingSelectorValue]
"""Mapping shape for an as-stored binding selector.

Named alias rather than an inline ``Mapping[str, ...]`` so consumer
code can express the type intent and discover the per-source typed
companion models declared in :mod:`_bindings` via the alias name.
"""
