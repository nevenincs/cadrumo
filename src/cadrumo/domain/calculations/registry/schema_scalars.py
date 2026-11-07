"""Scalar and annotated value types for registry schema models."""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from decimal import Decimal
from typing import Annotated, Literal, TypeAliasType

from pydantic import BeforeValidator

from ....core.country_code import COUNTRY_CODE_ALPHA2_PATTERN
from ....core.decimal.coercion import coerce_decimal
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.iban import BIC_SHAPE_RE, IBAN_SHAPE_RE, iban_mod_97, normalise_iban
from ....core.identity.documents import IdentityError, SpanishTaxIdFormat
from ....core.identity.nif_iva import normalise_nif_iva
from ....core.identity.tax_id import validate_spanish_tax_id
from ....core.period import StandardPeriodCode
from ....core.spanish_postcode import (
    SPANISH_MUNICIPALITY_CODE_PATTERN,
    SPANISH_POSTCODE_PATTERN,
    SPANISH_PROVINCE_CODE_PATTERN,
)
from .errors import RegistryValidationError

__all__ = [
    "CalendarDate",
    "CountryCode",
    "DecimalValue",
    "WorkbookCellRefStr",
    "registry_scalar_value_type",
    "validate_country_code",
    "validate_iban_string",
    "validate_period_code",
    "validate_registry_text_scalar",
]


@pydantic_validation_boundary
def _coerce_decimal(value: object) -> object:
    if isinstance(value, bool | float):
        raise RegistryValidationError("decimal values must not be booleans or floats")
    if isinstance(value, Decimal):
        return value
    result = coerce_decimal(value)
    return result if result is not None else value


DecimalValue = Annotated[Decimal, BeforeValidator(_coerce_decimal)]


def _validate_nif_value(value: object, tax_id_format: SpanishTaxIdFormat | None) -> object:
    """Validate one registry NIF using only the explicitly supplied format."""
    if not isinstance(value, str):
        raise RegistryValidationError(f"NIF value must be a string, got {type(value).__name__}")
    if not isinstance(tax_id_format, SpanishTaxIdFormat):
        raise RegistryValidationError("NIF validation requires an explicit Spanish tax-ID format")
    try:
        return validate_spanish_tax_id(value, tax_id_format)
    except IdentityError as exc:
        detail = exc.translated_message or str(exc)
        raise RegistryValidationError(f"invalid NIF / NIE / CIF identifier: {detail}") from exc


_STANDARD_PERIOD_CODES = frozenset(StandardPeriodCode)
_EXT_PATTERN = re.compile(r"^EXT-[1-4]T$")
_EVENT_PATTERN = re.compile(r"^EVENT-\d+$")


@pydantic_validation_boundary
def validate_period_code(value: object) -> object:
    """Validate a filing-period code against the registry-supported set.

    Accepted forms (from the fiscal-period inventory):

    - StandardPeriodCode: 1T-4T (quarterly), 1P-4P (instalment), 0A (annual), 01-12 (monthly).
    - ``EXT-1T``-``EXT-4T``: OSS extra-Union scheme quarters (modelo 369).
    - ``EVENT-N``: numbered event filings.

    Modellers introducing a new form must extend this validator.
    """
    if not isinstance(value, str):
        raise RegistryValidationError(f"period_code value must be a string, got {type(value).__name__}")
    if value in _STANDARD_PERIOD_CODES:
        return value
    if _EXT_PATTERN.match(value) or _EVENT_PATTERN.match(value):
        return value
    raise RegistryValidationError(f"period_code value {value!r} does not match a supported filing-period form")


_COUNTRY_CODE_RE = re.compile(rf"^{COUNTRY_CODE_ALPHA2_PATTERN}$")


@pydantic_validation_boundary
def validate_country_code(value: object) -> object:
    """Validate a two-character ISO 3166-1 alpha-2 country code.

    Format-only validation against the shared
    :data:`~cadrumo.core.country_code.COUNTRY_CODE_ALPHA2_PATTERN`: uppercase
    ASCII letters, exact length 2. A lowercase token is REFUSED rather than
    folded, matching
    :func:`~cadrumo.core.parsing.codes.normalise_iso_3166_alpha2_jurisdiction`: a
    country code on a casilla selects a regulatory treatment, so the operator
    declares the canonical code rather than having one guessed.

    Membership against the AEAT-supported country
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


CountryCode = Annotated[str, BeforeValidator(validate_country_code)]
"""Two-character country code for the registry boundary.

Used as the value type for casillas declaring
``data_type = "country_code"``. Membership against the
AEAT-supported country list is layered through per-casilla `enum`
constraints (Plan B) and semantic-role consistency (Plan C); this
alias enforces only the alpha-2 shape.
"""


@pydantic_validation_boundary
def validate_iban_string(value: object) -> object:
    """Validate an IBAN: country code, check digits, BBAN, and mod-97 residue.

    The validator strips whitespace and hyphens, uppercases, then
    enforces ISO 13616 shape (`CC kk BBAN`, total 15-34 chars) and
    the mod-97 check (the integer formed by moving the leading
    four chars to the tail and converting letters to digits must be
    congruent to 1 mod 97).
    """
    if not isinstance(value, str):
        raise RegistryValidationError(f"iban value must be a string, got {type(value).__name__}")
    canonical = normalise_iban(value)
    if not canonical:
        raise RegistryValidationError("iban value must not be blank")
    if not IBAN_SHAPE_RE.match(canonical):
        raise RegistryValidationError("iban value does not match the ISO 13616 shape")
    if iban_mod_97(canonical) != 1:
        raise RegistryValidationError("iban value fails the mod-97 check")
    return canonical


_MAX_NAME_LENGTH = 256


@pydantic_validation_boundary
def _validate_name_string(value: object) -> object:
    """Validate a personal or entity name: non-empty unicode within length bounds."""
    if not isinstance(value, str):
        raise RegistryValidationError(f"name value must be a string, got {type(value).__name__}")
    stripped = value.strip()
    if not stripped:
        raise RegistryValidationError("name value must not be blank")
    if len(stripped) > _MAX_NAME_LENGTH:
        raise RegistryValidationError(f"name value exceeds {_MAX_NAME_LENGTH} characters: {len(stripped)}")
    return stripped


_NIF_IVA_PREFIX_LENGTH = 2
_NIF_IVA_RE = re.compile(r"[A-Z]{2}[A-Z0-9]{1,64}")


@pydantic_validation_boundary
def _validate_nif_iva_string(value: object) -> object:
    """Validate an intracomunitario NIF-IVA: ISO country prefix plus identifier body."""
    if not isinstance(value, str):
        raise RegistryValidationError(f"nif_iva value must be a string, got {type(value).__name__}")
    canonical = normalise_nif_iva(value)
    if _NIF_IVA_RE.fullmatch(canonical) is None:
        raise RegistryValidationError(
            f"nif_iva value {value!r} must start with a two-letter country code followed by alphanumeric characters",
        )
    from .form_codes import form_codes_in_scope

    codes = form_codes_in_scope("nif-iva-country-format-catalogue")
    if codes is not None:
        shortest, longest = codes.integer("nif_iva.body_min_length"), codes.integer("nif_iva.body_max_length")
        if not shortest <= len(canonical) - _NIF_IVA_PREFIX_LENGTH <= longest:
            raise RegistryValidationError(
                f"nif_iva value {value!r} must start with a two-letter country code "
                f"followed by {shortest}-{longest} alphanumeric characters",
            )
    return canonical


@pydantic_validation_boundary
def _validate_ccaa_code(value: object) -> object:
    """Validate that a value has the shape of a comunidad code; it binds no code to a community."""
    if not isinstance(value, str):
        raise RegistryValidationError(f"ccaa_code value must be a string, got {type(value).__name__}")
    from .form_codes import form_codes_in_scope

    codes = form_codes_in_scope("comunidad-code-shape")
    if codes is not None and value not in codes.codes("codes"):
        raise RegistryValidationError(
            f"ccaa_code value {value!r} must be a two-digit Spanish autonomous-community code",
        )
    return value


_PROVINCE_CODE_RE = re.compile(rf"^{SPANISH_PROVINCE_CODE_PATTERN}$")


@pydantic_validation_boundary
def _validate_province_code(value: object) -> object:
    """Validate a Spanish province code (01-52)."""
    if not isinstance(value, str):
        raise RegistryValidationError(f"province_code value must be a string, got {type(value).__name__}")
    if not _PROVINCE_CODE_RE.match(value):
        raise RegistryValidationError(
            f"province_code value {value!r} must be a two-digit Spanish province code (01-52)",
        )
    return value


_POSTAL_CODE_RE = re.compile(rf"^{SPANISH_POSTCODE_PATTERN}$")


@pydantic_validation_boundary
def _validate_postal_code(value: object) -> object:
    """Validate a Spanish postal code against the one shape authority.

    Five digits whose leading pair is a real province code. The refusal stays
    here, in the registry's own error type, because a caller loading a registry
    fragment must be told which fragment is malformed; only the SHAPE is shared.
    """
    if not isinstance(value, str):
        raise RegistryValidationError(f"postal_code value must be a string, got {type(value).__name__}")
    if not _POSTAL_CODE_RE.match(value):
        raise RegistryValidationError(f"postal_code value {value!r} must be a five-digit Spanish postal code")
    return value


_MUNICIPALITY_CODE_RE = re.compile(SPANISH_MUNICIPALITY_CODE_PATTERN)


@pydantic_validation_boundary
def _validate_municipality_code(value: object) -> object:
    """Validate a five-digit INE municipality code.

    An INE code is a province code followed by a three-digit municipality
    number, so it reads the same province alternation as a postcode without
    being the same concept: ``28079`` is Madrid the municipality, not a postal
    district.
    """
    if not isinstance(value, str):
        raise RegistryValidationError(f"municipality_code value must be a string, got {type(value).__name__}")
    if not _MUNICIPALITY_CODE_RE.match(value):
        raise RegistryValidationError(
            f"municipality_code value {value!r} must be an INE code: a province code (01-52) followed by three digits",
        )
    return value


@pydantic_validation_boundary
def _validate_bic_string(value: object) -> object:
    """Validate a SWIFT BIC (ISO 9362): 8 or 11 characters."""
    if not isinstance(value, str):
        raise RegistryValidationError(f"bic value must be a string, got {type(value).__name__}")
    canonical = value.replace(" ", "").upper()
    if not BIC_SHAPE_RE.match(canonical):
        raise RegistryValidationError(f"bic value {value!r} must be 8 or 11 alphanumeric characters per ISO 9362")
    return canonical


# Keep a named runtime alias while Semgrep cannot parse this PEP 695 declaration.
RegistryScalarValueType = TypeAliasType(  # noqa: UP040
    "RegistryScalarValueType", Literal["decimal", "int", "str", "bool", "date"]
)
"""Runtime family for a registry casilla ``data_type`` declaration."""


REGISTRY_SCALAR_VALUE_TYPES: dict[str, RegistryScalarValueType] = {
    "decimal": "decimal",
    "money": "decimal",
    "ratio": "decimal",
    "integer": "int",
    "year": "int",
    "text": "str",
    "nif": "str",
    "nif_iva": "str",
    "name": "str",
    "period_code": "str",
    "country_code": "str",
    "ccaa_code": "str",
    "province_code": "str",
    "municipality_code": "str",
    "postal_code": "str",
    "iban": "str",
    "bic": "str",
    "boolean": "bool",
    "date": "date",
}

# Called directly rather than as pydantic validators, so each entry is the
# undecorated callable and refuses with the registry error, not its pydantic
# ``ValueError`` translation.
_REGISTRY_TEXT_SCALAR_VALIDATORS: dict[str, Callable[[object], object]] = {
    "text": lambda value: value,
    "nif_iva": inspect.unwrap(_validate_nif_iva_string),
    "name": inspect.unwrap(_validate_name_string),
    "period_code": inspect.unwrap(validate_period_code),
    "country_code": inspect.unwrap(validate_country_code),
    "ccaa_code": inspect.unwrap(_validate_ccaa_code),
    "province_code": inspect.unwrap(_validate_province_code),
    "municipality_code": inspect.unwrap(_validate_municipality_code),
    "postal_code": inspect.unwrap(_validate_postal_code),
    "iban": inspect.unwrap(validate_iban_string),
    "bic": inspect.unwrap(_validate_bic_string),
}


def registry_scalar_value_type(data_type: str) -> RegistryScalarValueType:
    """Return the runtime family declared by a registry scalar data type."""
    try:
        return REGISTRY_SCALAR_VALUE_TYPES[data_type]
    except KeyError as exc:
        raise RegistryValidationError(f"unsupported registry casilla data type {data_type!r}") from exc


def validate_registry_text_scalar(
    data_type: str,
    value: object,
    *,
    tax_id_format: SpanishTaxIdFormat | None = None,
) -> str:
    """Canonicalise one text-family casilla value through its declared validator."""
    if registry_scalar_value_type(data_type) != "str":
        raise RegistryValidationError(f"registry casilla data type {data_type!r} is not a text scalar")
    if not isinstance(value, str):
        raise RegistryValidationError(f"{data_type} value must be a string, got {type(value).__name__}")
    stripped = value.strip()
    # The generic "text" family is the free-form escape hatch (identity
    # validator, no semantic contract) and covers AEAT fixed-width fields the
    # DR declares optional (space-padded when not applicable, e.g. Modelo
    # 720's persona-con-quien-relacionarse). Every other text-family type has
    # a real validator for which blank is genuinely invalid.
    if not stripped and data_type != "text":
        raise RegistryValidationError(f"{data_type} value must not be blank")
    result = (
        _validate_nif_value(stripped, tax_id_format)
        if data_type == "nif"
        else _REGISTRY_TEXT_SCALAR_VALIDATORS[data_type](stripped)
    )
    if not isinstance(result, str):
        raise RegistryValidationError(f"{data_type} validator did not return a string")
    return result


_DATE_DDMMAAAA_RE = re.compile(r"^(0[1-9]|[12]\d|3[01])(0[1-9]|1[0-2])\d{4}$")
_DATE_ISO_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


@pydantic_validation_boundary
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


@pydantic_validation_boundary
def _validate_workbook_cell_ref_str(value: object) -> object:
    if isinstance(value, str) and not _WORKBOOK_CELL_REF_RE.match(value):
        raise RegistryValidationError(f"invalid workbook cell reference {value!r}")
    return value


WorkbookCellRefStr = Annotated[str, BeforeValidator(_validate_workbook_cell_ref_str)]
