"""Scalar and annotated value types for registry schema models."""

from __future__ import annotations

import re
from collections.abc import Callable
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, SerializeAsAny

from ....core import IBAN_SHAPE_RE, iban_mod_97, normalise_iban
from ....core.decimal import coerce_decimal
from ....core.filing_year import FILING_YEAR_MAX, FILING_YEAR_MIN
from ....core.identity import IdentityError, validate_spanish_tax_id
from ....core.period import StandardPeriodCode
from ....core.spanish_postcode import SPANISH_POSTCODE_PATTERN, SPANISH_PROVINCE_CODE_PATTERN
from .errors import RegistryValidationError

__all__ = [
    "BicString",
    "BindingSelector",
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
    "coerce_modelo_year",
    "registry_scalar_value_type",
    "validate_country_code",
    "validate_iban_string",
    "validate_nif_string",
    "validate_period_code",
    "validate_registry_text_scalar",
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

    Delegates to the shared `validate_spanish_tax_id` algorithm exposed by
    the single `cadrumo.core.identity` facade and re-raises domain
    `IdentityError` as `RegistryValidationError` so the schema boundary
    surfaces identifier-format problems through its established error type.
    """
    if not isinstance(value, str):
        raise RegistryValidationError(f"NIF value must be a string, got {type(value).__name__}")
    try:
        return validate_spanish_tax_id(value)
    except IdentityError as exc:
        detail = exc.translated_message or str(exc)
        raise RegistryValidationError(f"invalid NIF / NIE / CIF identifier: {detail}") from exc


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


ModeloYear = Annotated[int, BeforeValidator(_coerce_modelo_year), Field(ge=FILING_YEAR_MIN, le=FILING_YEAR_MAX)]
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
    canonical = normalise_iban(value)
    if not canonical:
        raise RegistryValidationError("iban value must not be blank")
    if not IBAN_SHAPE_RE.match(canonical):
        raise RegistryValidationError(f"iban value {value!r} does not match the ISO 13616 shape")
    if iban_mod_97(canonical) != 1:
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


# A general-purpose SHAPE check on a two-digit comunidad code: a contiguous
# 01-19, one per autonomous community plus the two autonomous cities. It asserts
# membership only -- it binds no code to any particular community -- so it can
# confirm that an authoring value looks like a comunidad code and nothing more.
#
# It is deliberately not any single modelo's numbering, and the modelos differ.
# Modelo 100 accepts 01-13 and 16-20: it assigns nothing to 14 or 15, which this
# set admits, and assigns 20 to "no residente", which this set rejects. So a
# casilla carrying a Modelo 100 comunidad must take its código from that modelo's
# own authority (``modelo100_ccaa_codigo`` in ``domain.contribuyente``, grounded
# in the bundled record-design XSD) rather than from this check, which cannot
# tell one community from another and would pass a wrong código unchanged.
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
    """Validate that a value has the shape of a two-digit comunidad code (01-19)."""
    if not isinstance(value, str):
        raise RegistryValidationError(f"ccaa_code value must be a string, got {type(value).__name__}")
    if value not in _CCAA_CODES:
        raise RegistryValidationError(
            f"ccaa_code value {value!r} must be a two-digit Spanish autonomous-community code (01-19)",
        )
    return value


CCAACode = Annotated[str, BeforeValidator(_validate_ccaa_code)]
"""Generic two-digit comunidad code for the registry boundary.

Checks shape only; a modelo-specific código comes from that modelo's own
authority. See the note on the accepted set above.
"""


_PROVINCE_CODE_RE = re.compile(rf"^{SPANISH_PROVINCE_CODE_PATTERN}$")


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


_POSTAL_CODE_RE = re.compile(rf"^{SPANISH_POSTCODE_PATTERN}$")


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


PostalCode = Annotated[str, BeforeValidator(_validate_postal_code)]
"""Five-digit Spanish postal code for the registry boundary."""


_MUNICIPALITY_CODE_RE = re.compile(rf"^{SPANISH_PROVINCE_CODE_PATTERN}[0-9]{{3}}$")


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
            f"municipality_code value {value!r} must be an INE code: "
            "a province code (01-52) followed by three digits",
        )
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


type RegistryScalarValueType = Literal["decimal", "int", "str", "bool", "date"]
"""Runtime family for a registry casilla ``data_type`` declaration."""


_REGISTRY_SCALAR_VALUE_TYPES: dict[str, RegistryScalarValueType] = {
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

_REGISTRY_TEXT_SCALAR_VALIDATORS: dict[str, Callable[[object], object]] = {
    "text": lambda value: value,
    "nif": _validate_nif_string,
    "nif_iva": _validate_nif_iva_string,
    "name": _validate_name_string,
    "period_code": _validate_period_code,
    "country_code": _validate_country_code,
    "ccaa_code": _validate_ccaa_code,
    "province_code": _validate_province_code,
    "municipality_code": _validate_municipality_code,
    "postal_code": _validate_postal_code,
    "iban": _validate_iban_string,
    "bic": _validate_bic_string,
}


def registry_scalar_value_type(data_type: str) -> RegistryScalarValueType:
    """Return the runtime family declared by a registry scalar data type."""
    try:
        return _REGISTRY_SCALAR_VALUE_TYPES[data_type]
    except KeyError as exc:
        raise RegistryValidationError(f"unsupported registry casilla data type {data_type!r}") from exc


def validate_registry_text_scalar(data_type: str, value: object) -> str:
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
    validator = _REGISTRY_TEXT_SCALAR_VALIDATORS[data_type]
    result = validator(stripped)
    if not isinstance(result, str):
        raise RegistryValidationError(f"{data_type} validator did not return a string")
    return result


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
"""Closed union of the value shapes a raw binding-selector entry can hold."""

BindingSelectorMap = dict[str, BindingSelectorValue]
"""Authoring/input mapping shape for binding selectors before family hydration.

Registry TOML and tests still supply selector payloads as ordinary dictionaries.
``DataBindingDefinition`` immediately hydrates that mapping through the
per-source selector model registered in :mod:`_bindings`, so the stored binding
field is no longer this broad map.
"""

BindingSelector = SerializeAsAny[BaseModel]
"""Stored binding selector payload after source-family hydration.

The concrete value is one of the frozen per-source pydantic selector models
registered by ``selector_model_for_source``. ``SerializeAsAny`` preserves the
concrete model's fields during ``model_dump``/``model_dump_json`` instead of
serialising through the empty ``BaseModel`` surface.
"""

# Public-internal names let the schema facade preserve its historical private
# aliases without coupling its implementation to this module's private helpers.
coerce_modelo_year = _coerce_modelo_year
validate_country_code = _validate_country_code
validate_iban_string = _validate_iban_string
validate_nif_string = _validate_nif_string
validate_period_code = _validate_period_code
