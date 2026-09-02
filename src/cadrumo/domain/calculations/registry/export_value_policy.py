"""Canonical value-policy projection for fixed-width registry export fields."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from fractions import Fraction
from functools import partial
from math import isfinite
from typing import Annotated, Final

from pydantic import BeforeValidator

from .errors import RegistryValidationError


class SelectedUnselectedFlag(StrEnum):
    """The two ASCII characters a selected/unselected export field may contain.

    Named because the tokens carry meaning the digits do not: the field is a checkbox,
    not a quantity. Both the projector and the validator tested the pair separately, and
    both error messages already said "exactly ASCII 0 or 1" -- the rule was stated three
    times and declared none.
    """

    UNSELECTED = "0"
    SELECTED = "1"


SELECTED_UNSELECTED_VALUES: Final[frozenset[SelectedUnselectedFlag]] = frozenset(SelectedUnselectedFlag)
"""Both flag characters, derived from the enum so the two checks cannot disagree."""


class ExportValuePolicy(StrEnum):
    """Closed runtime transformations from semantic values to AEAT wire tokens."""

    SELECTED_1_UNSELECTED_0 = "selected-1-unselected-0"
    FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS = "four-digit-year-final-two-digits"
    UNSIGNED_INTEGER = "unsigned-integer"
    IMPLIED_DECIMAL = "implied-decimal"
    YYYYMMDD = "yyyymmdd"
    DDMMYYYY = "ddmmyyyy"
    ENUMERATED_DIGITS = "enumerated-digits"
    DIGIT_STRING = "digit-string"
    IDENTIFIER_DIGITS = "identifier-digits"
    FOUR_DIGIT_YEAR = "four-digit-year"
    TWO_DIGIT_MONTH = "two-digit-month"
    TWO_DIGIT_DAY = "two-digit-day"
    #: A slot AEAT typed numeric that carries alphanumeric prose. AEAT's own Nota
    #: 1 defines the column exactly -- "A (Alfabetico) An (Alfanumerico), Num
    #: (Numerico sin signo) o N (Numerico con signo)" -- so "Num" on a
    #: 100-position "Descripcion del elemento patrimonial" is a publication error,
    #: not a convention. There is no numeric reading of that slot to derive, and
    #: the surrounding rows are typed identically, so the mistyping is not
    #: recoverable from the design. This policy is how a REVIEWED profile states
    #: the real representation; it is never inferred from width or description.
    MISTYPED_ALPHANUMERIC_TEXT = "mistyped-alphanumeric-text"
    #: AEAT prints some quantities as a parent row subdivided into a printed
    #: "Parte entera" row and a printed "Parte decimal" row. The record-design
    #: parser folds that subdivision on exact tiling and the export IR descends
    #: to the LEAVES, so a layout necessarily carries two fields where the
    #: declared value is one -- and the export path resolves values per CASILLA,
    #: handing BOTH leaves the identical whole value. These two policies are how
    #: each leaf states which part of that value it writes; the field's own
    #: declared length fixes how many digits the part occupies. Neither part is
    #: invertible alone, so parsing one retains the wire token rather than
    #: presenting itself as a reconstructed quantity.
    INTEGER_PART = "integer-part"
    FRACTIONAL_DIGITS = "fractional-digits"


@dataclass(frozen=True, slots=True)
class ParsedExportPolicyWireValue:
    """Validated wire value retained when its source semantic value is not invertible."""

    policy: ExportValuePolicy
    raw: str


type ParsedExportPolicyValue = Decimal | str | bool | int | ParsedExportPolicyWireValue | None


def coerce_export_value_policy(value: object) -> object:
    """Hydrate a declared policy token while leaving unknown values to strict validation."""
    if value is None or isinstance(value, ExportValuePolicy):
        return value
    if isinstance(value, str):
        try:
            return ExportValuePolicy(value)
        except ValueError:
            return value
    return value


RequiredExportValuePolicyValue = Annotated[ExportValuePolicy, BeforeValidator(coerce_export_value_policy)]
ExportValuePolicyValue = RequiredExportValuePolicyValue | None

_WIRE_LENGTH_BY_POLICY: dict[ExportValuePolicy, int] = {
    ExportValuePolicy.SELECTED_1_UNSELECTED_0: 1,
    ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS: 2,
    ExportValuePolicy.YYYYMMDD: 8,
    ExportValuePolicy.DDMMYYYY: 8,
    ExportValuePolicy.FOUR_DIGIT_YEAR: 4,
    ExportValuePolicy.TWO_DIGIT_MONTH: 2,
    ExportValuePolicy.TWO_DIGIT_DAY: 2,
}


def export_value_policy_wire_length(policy: ExportValuePolicy) -> int | None:
    """Return a fixed policy width, or ``None`` when the field declares it."""
    return _WIRE_LENGTH_BY_POLICY.get(policy)


def project_export_value(policy: ExportValuePolicy | None, value: object) -> object:
    """Project one semantic value to its exact declared wire token.

    ``None`` is deliberately inert: it is not an inference hook and does not
    select a policy from field width, type, identifier, or historical layout.
    """
    if policy is None:
        return value
    if isinstance(value, ParsedExportPolicyWireValue):
        if policy not in _RETAINED_WIRE_POLICIES or value.policy is not policy:
            raise RegistryValidationError(
                "parsed export wire values are admitted only for the matching non-invertible policy",
            )
        validate_export_wire_value(policy, value.raw)
        return value.raw
    projector = _PROJECTOR_BY_POLICY.get(policy)
    if projector is None:
        raise RegistryValidationError(f"unknown export value policy {policy!r}")
    return projector(value)


def policy_defines_absent_slot(policy: ExportValuePolicy | None) -> bool:
    """Whether ``policy`` assigns its OWN meaning to a slot carrying no value.

    An unselected checkbox is not an absent number: its policy declares that the
    empty slot means ``0``, so the value must reach the projector. Every other
    policy leaves absence to the field's declared blank fill, which is what
    AEAT's designs state ("los campos numericos que no tengan contenido se
    rellenaran a ceros"). Named rather than inlined at the call site so the
    exception stays one auditable list instead of a condition readers must
    re-derive.
    """
    return policy in _POLICIES_DEFINING_ABSENCE


def validate_export_wire_value(policy: ExportValuePolicy | None, raw: str) -> None:
    """Refuse a wire token that contradicts its declared value policy."""
    if policy is None:
        return
    validator = _WIRE_VALIDATOR_BY_POLICY.get(policy)
    if validator is None:
        raise RegistryValidationError(f"unknown export value policy {policy!r}")
    validator(raw)


def normalize_parsed_export_policy_value(
    policy: ExportValuePolicy | None,
    raw: str,
    parsed: ParsedExportPolicyValue,
) -> ParsedExportPolicyValue:
    """Return a renderer-admissible semantic value for canonical parsed wire."""
    if policy in {
        ExportValuePolicy.FOUR_DIGIT_YEAR,
        ExportValuePolicy.TWO_DIGIT_MONTH,
        ExportValuePolicy.TWO_DIGIT_DAY,
    }:
        return int(raw)
    if policy is not None and policy in _RETAINED_WIRE_POLICIES:
        return ParsedExportPolicyWireValue(policy=policy, raw=raw)
    return parsed


def _project_selected_unselected(value: object) -> str:
    if value is None:
        return SelectedUnselectedFlag.UNSELECTED
    if isinstance(value, str):
        return _project_selected_unselected_string(value)
    if isinstance(value, bool):
        return "1" if value else "0"
    return _project_selected_unselected_number(value)


def _project_selected_unselected_string(value: str) -> str:
    if value == "":
        return SelectedUnselectedFlag.UNSELECTED
    if value in SELECTED_UNSELECTED_VALUES:
        return value
    raise RegistryValidationError(
        "selected/unselected export string must be empty or exactly ASCII 0 or 1",
    )


def _project_selected_unselected_number(value: object) -> str:
    if isinstance(value, Decimal) and not value.is_finite():
        raise RegistryValidationError("selected/unselected export numeric value must be finite")
    if isinstance(value, float) and not isfinite(value):
        raise RegistryValidationError("selected/unselected export numeric value must be finite")
    if isinstance(value, (int, float, Decimal, Fraction)):
        if value == 0:
            return SelectedUnselectedFlag.UNSELECTED
        if value == 1:
            return "1"
    raise RegistryValidationError(
        "selected/unselected export value must be absent, empty, False, True, or exact numeric/string 0 or 1",
    )


def _project_four_digit_year(value: object) -> str:
    if isinstance(value, bool):
        raise RegistryValidationError("short-year export value must be a four-digit year, not boolean")
    if isinstance(value, int):
        if 1000 <= value <= 9999:
            return str(value)[-2:]
        raise RegistryValidationError("short-year export integer must contain exactly four digits")
    if isinstance(value, str) and len(value) == 4 and value.isascii() and value.isdigit():
        return value[-2:]
    raise RegistryValidationError("short-year export value must be a four-digit integer or four ASCII-digit string")


def _project_unsigned_integer(value: object) -> Decimal:
    number = _strict_decimal(value, label="unsigned integer")
    if number.is_signed() or number != number.to_integral_value():
        raise RegistryValidationError("unsigned integer export value must be finite, integral, and non-negative")
    return number


def _project_split_part(policy: ExportValuePolicy, value: object) -> Decimal:
    """Admit the WHOLE quantity a split part is cut from, refusing a negative.

    Both parts are handed the same value the casilla carries, so this projector
    validates the quantity and leaves the cut to the codec, which is the only
    layer that knows how many digits the part's own slot holds. The designs that
    print these subdivisions state the sin-signo convention and print a separate
    signo field where they want one, so a negative quantity is refused here
    rather than silently rendered as its magnitude across the parts.
    """
    number = _strict_decimal(value, label=policy.value)
    if number.is_signed():
        raise RegistryValidationError(f"{policy.value} export value must be non-negative")
    return number


def _project_unsigned_decimal(value: object) -> Decimal:
    number = _strict_decimal(value, label="implied-decimal")
    if number.is_signed():
        raise RegistryValidationError("implied-decimal export value must be non-negative")
    return number


def _strict_decimal(value: object, *, label: str) -> Decimal:
    if isinstance(value, bool) or value is None or isinstance(value, (float, Fraction)):
        raise RegistryValidationError(f"{label} export value must be an exact integer, Decimal, or canonical string")
    if isinstance(value, int):
        number = Decimal(value)
    elif isinstance(value, Decimal):
        number = value
    elif isinstance(value, str):
        number = _strict_decimal_from_string(value, label=label)
    else:
        raise RegistryValidationError(f"{label} export value must be an exact integer, Decimal, or canonical string")
    if not number.is_finite():
        raise RegistryValidationError(f"{label} export value must be finite")
    return number


def _strict_decimal_from_string(value: str, *, label: str) -> Decimal:
    if not value or value.strip() != value or value.startswith("+"):
        raise RegistryValidationError(f"{label} export string is not canonical")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise RegistryValidationError(f"{label} export string is not numeric") from exc
    if format(number, "f") != value:
        raise RegistryValidationError(f"{label} export string is not canonical")
    return number


def _project_digit_identity(policy: ExportValuePolicy, value: object) -> str:
    if not isinstance(value, str):
        raise RegistryValidationError(f"{policy.value} export value must be an ASCII digit string")
    _require_ascii_digits(value, label=policy.value)
    return value


def _project_full_year(value: object) -> str:
    if isinstance(value, bool):
        raise RegistryValidationError("four-digit-year export value must not be boolean")
    if type(value) is date:
        # A date SPLIT across printed year/month/day slots reaches each slot as
        # the whole date, exactly as a split amount reaches both of its halves.
        # Taking the component the policy names is the same cut, and the exact
        # type test mirrors the whole-date projectors so a datetime still
        # refuses rather than silently dropping its time.
        raw = f"{value.year:04d}"
    elif isinstance(value, int):
        raw = str(value)
    elif isinstance(value, str):
        raw = value
    else:
        raise RegistryValidationError("four-digit-year export value must be an integer or ASCII digit string")
    _validate_full_year(raw)
    return raw


def _project_calendar_part(value: object, *, label: str, minimum: int, maximum: int) -> str:
    if isinstance(value, bool):
        raise RegistryValidationError(f"two-digit-{label} export value must not be boolean")
    if type(value) is date:
        number = value.month if label == "month" else value.day
    elif isinstance(value, int):
        number = value
    elif isinstance(value, str) and 1 <= len(value) <= 2 and value.isascii() and value.isdigit():
        number = int(value)
    else:
        raise RegistryValidationError(f"two-digit-{label} export value must be an integer or one/two ASCII digits")
    if not minimum <= number <= maximum:
        raise RegistryValidationError(f"two-digit-{label} export value is outside {minimum}..{maximum}")
    return f"{number:02d}"


def _project_yyyymmdd(value: object) -> str:
    if type(value) is date:
        return value.strftime("%Y%m%d")
    if not isinstance(value, str):
        raise RegistryValidationError("yyyymmdd export value must be a date or exactly eight ASCII digits")
    _validate_yyyymmdd(value)
    return value


def _project_ddmmyyyy(value: object) -> str:
    if type(value) is date:
        return value.strftime("%d%m%Y")
    if not isinstance(value, str):
        raise RegistryValidationError("ddmmyyyy export value must be a date or exactly eight ASCII digits")
    _validate_ddmmyyyy(value)
    return value


def _project_mistyped_alphanumeric_text(value: object) -> str:
    if not isinstance(value, str):
        raise RegistryValidationError(
            "mistyped-alphanumeric-text export value must be a string; the slot carries prose, "
            "not the number AEAT's naturaleza column claims",
        )
    _validate_mistyped_alphanumeric_text(value)
    return value


def _validate_mistyped_alphanumeric_text(raw: str) -> None:
    # A fixed-width record is one unbroken line, so a control character in a
    # prose slot does not merely look wrong -- it tears the record. Everything
    # else the slot may legitimately carry, digits included: a descripcion
    # reading "1234" is a description, not a number.
    if any(character < " " or character == "\x7f" for character in raw):
        raise RegistryValidationError(
            "mistyped-alphanumeric-text export field must not contain control characters",
        )


def _require_ascii_digits(raw: str, *, label: str) -> None:
    if not raw or not raw.isascii() or not raw.isdigit():
        raise RegistryValidationError(f"{label} export field must contain only non-empty ASCII digits")


def _validate_selected_unselected(raw: str) -> None:
    if raw not in SELECTED_UNSELECTED_VALUES:
        raise RegistryValidationError("selected/unselected export field must contain exactly ASCII 0 or 1")


def _validate_short_year(raw: str) -> None:
    if len(raw) != 2 or not raw.isascii() or not raw.isdigit():
        raise RegistryValidationError("short-year export field must contain exactly two ASCII digits")


def _validate_full_year(raw: str) -> None:
    if len(raw) != 4 or not raw.isascii() or not raw.isdigit() or not 1000 <= int(raw) <= 9999:
        raise RegistryValidationError("four-digit-year export field must contain a year from 1000 through 9999")


def _validate_calendar_part(raw: str, *, label: str, minimum: int, maximum: int) -> None:
    if len(raw) != 2 or not raw.isascii() or not raw.isdigit() or not minimum <= int(raw) <= maximum:
        raise RegistryValidationError(
            f"two-digit-{label} export field must contain exactly two ASCII digits in {minimum}..{maximum}",
        )


def _validate_yyyymmdd(raw: str) -> None:
    if len(raw) != 8 or not raw.isascii() or not raw.isdigit():
        raise RegistryValidationError("yyyymmdd export field must contain exactly eight ASCII digits")
    try:
        date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))
    except ValueError as exc:
        raise RegistryValidationError("yyyymmdd export field must contain a real calendar date") from exc


def _validate_ddmmyyyy(raw: str) -> None:
    if len(raw) != 8 or not raw.isascii() or not raw.isdigit():
        raise RegistryValidationError("ddmmyyyy export field must contain exactly eight ASCII digits")
    try:
        date(int(raw[4:]), int(raw[2:4]), int(raw[:2]))
    except ValueError as exc:
        raise RegistryValidationError("ddmmyyyy export field must contain a real calendar date") from exc


_PROJECTOR_BY_POLICY: dict[ExportValuePolicy, Callable[[object], object]] = {
    ExportValuePolicy.SELECTED_1_UNSELECTED_0: _project_selected_unselected,
    ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS: _project_four_digit_year,
    ExportValuePolicy.UNSIGNED_INTEGER: _project_unsigned_integer,
    ExportValuePolicy.ENUMERATED_DIGITS: _project_unsigned_integer,
    ExportValuePolicy.IMPLIED_DECIMAL: _project_unsigned_decimal,
    ExportValuePolicy.YYYYMMDD: _project_yyyymmdd,
    ExportValuePolicy.DDMMYYYY: _project_ddmmyyyy,
    ExportValuePolicy.DIGIT_STRING: partial(_project_digit_identity, ExportValuePolicy.DIGIT_STRING),
    ExportValuePolicy.IDENTIFIER_DIGITS: partial(_project_digit_identity, ExportValuePolicy.IDENTIFIER_DIGITS),
    ExportValuePolicy.FOUR_DIGIT_YEAR: _project_full_year,
    ExportValuePolicy.TWO_DIGIT_MONTH: partial(_project_calendar_part, label="month", minimum=1, maximum=12),
    ExportValuePolicy.TWO_DIGIT_DAY: partial(_project_calendar_part, label="day", minimum=1, maximum=31),
    ExportValuePolicy.MISTYPED_ALPHANUMERIC_TEXT: _project_mistyped_alphanumeric_text,
    ExportValuePolicy.INTEGER_PART: partial(_project_split_part, ExportValuePolicy.INTEGER_PART),
    ExportValuePolicy.FRACTIONAL_DIGITS: partial(_project_split_part, ExportValuePolicy.FRACTIONAL_DIGITS),
}

#: Policies that give an EMPTY slot a meaning of their own, so absence must be
#: projected rather than filled. Only the checkbox does: its unselected state is
#: the declared ``0``, not a missing number.
_POLICIES_DEFINING_ABSENCE: frozenset[ExportValuePolicy] = frozenset(
    {ExportValuePolicy.SELECTED_1_UNSELECTED_0},
)

#: Policies whose wire token cannot be inverted to the semantic value it came
#: from, so a parse retains the token itself. A split part carries only some of
#: the quantity's digits; the short year discards the century.
_RETAINED_WIRE_POLICIES: frozenset[ExportValuePolicy] = frozenset(
    {
        ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS,
        ExportValuePolicy.INTEGER_PART,
        ExportValuePolicy.FRACTIONAL_DIGITS,
    },
)

_WIRE_VALIDATOR_BY_POLICY: dict[ExportValuePolicy, Callable[[str], None]] = {
    ExportValuePolicy.SELECTED_1_UNSELECTED_0: _validate_selected_unselected,
    ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS: _validate_short_year,
    ExportValuePolicy.UNSIGNED_INTEGER: partial(_require_ascii_digits, label=ExportValuePolicy.UNSIGNED_INTEGER.value),
    ExportValuePolicy.IMPLIED_DECIMAL: partial(_require_ascii_digits, label=ExportValuePolicy.IMPLIED_DECIMAL.value),
    ExportValuePolicy.ENUMERATED_DIGITS: partial(
        _require_ascii_digits,
        label=ExportValuePolicy.ENUMERATED_DIGITS.value,
    ),
    ExportValuePolicy.DIGIT_STRING: partial(_require_ascii_digits, label=ExportValuePolicy.DIGIT_STRING.value),
    ExportValuePolicy.INTEGER_PART: partial(_require_ascii_digits, label=ExportValuePolicy.INTEGER_PART.value),
    ExportValuePolicy.FRACTIONAL_DIGITS: partial(
        _require_ascii_digits,
        label=ExportValuePolicy.FRACTIONAL_DIGITS.value,
    ),
    ExportValuePolicy.IDENTIFIER_DIGITS: partial(
        _require_ascii_digits,
        label=ExportValuePolicy.IDENTIFIER_DIGITS.value,
    ),
    ExportValuePolicy.FOUR_DIGIT_YEAR: _validate_full_year,
    ExportValuePolicy.TWO_DIGIT_MONTH: partial(_validate_calendar_part, label="month", minimum=1, maximum=12),
    ExportValuePolicy.TWO_DIGIT_DAY: partial(_validate_calendar_part, label="day", minimum=1, maximum=31),
    ExportValuePolicy.YYYYMMDD: _validate_yyyymmdd,
    ExportValuePolicy.DDMMYYYY: _validate_ddmmyyyy,
    ExportValuePolicy.MISTYPED_ALPHANUMERIC_TEXT: _validate_mistyped_alphanumeric_text,
}

__all__ = [
    "ExportValuePolicy",
    "ExportValuePolicyValue",
    "ParsedExportPolicyValue",
    "ParsedExportPolicyWireValue",
    "RequiredExportValuePolicyValue",
    "coerce_export_value_policy",
    "export_value_policy_wire_length",
    "normalize_parsed_export_policy_value",
    "project_export_value",
    "validate_export_wire_value",
]
