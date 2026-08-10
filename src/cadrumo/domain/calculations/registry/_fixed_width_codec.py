"""Canonical semantic-to-wire codec for registry fixed-width export fields."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Annotated, Literal, Protocol

from pydantic import BeforeValidator

from ....core.decimal import coerce_fixed_width_decimal
from ....core.money import round_to_cents
from ._errors import RegistryValidationError
from ._export_value_policy import (
    ExportValuePolicy,
    project_export_value,
    validate_export_wire_value,
)


class ExportPadding(StrEnum):
    """Closed fixed-width padding axis declared by registry fields."""

    LEFT_ZERO = "left_zero"
    LEFT_SPACE = "left_space"
    RIGHT_SPACE = "right_space"
    NONE = "none"


class ExportJustification(StrEnum):
    """Closed fixed-width alignment axis declared by registry fields."""

    LEFT = "left"
    RIGHT = "right"
    NONE = "none"


class ExportEncoding(StrEnum):
    """Closed character encodings admitted by fixed-width registry records."""

    ASCII = "ascii"
    CP1252 = "cp1252"
    ISO_8859_1 = "iso-8859-1"
    ISO_8859_15 = "iso-8859-15"
    LATIN_1 = "latin-1"


def _coerce_closed_axis(value: object, axis: type[StrEnum]) -> object:
    if isinstance(value, axis):
        return value
    if isinstance(value, str):
        try:
            return axis(value)
        except ValueError:
            return value
    return value


ExportPaddingValue = Annotated[
    ExportPadding,
    BeforeValidator(lambda value: _coerce_closed_axis(value, ExportPadding)),
]
ExportJustificationValue = Annotated[
    ExportJustification,
    BeforeValidator(lambda value: _coerce_closed_axis(value, ExportJustification)),
]
ExportEncodingValue = Annotated[
    ExportEncoding,
    BeforeValidator(lambda value: _coerce_closed_axis(value, ExportEncoding)),
]


class _ExportField(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def length(self) -> int | None: ...

    @property
    def kind(self) -> object: ...

    @property
    def literal(self) -> str | None: ...

    @property
    def data_type(self) -> Literal["text", "integer", "decimal", "money", "date", "boolean"]: ...

    @property
    def padding(self) -> ExportPadding: ...

    @property
    def justification(self) -> ExportJustification: ...

    @property
    def decimals(self) -> int | None: ...

    @property
    def signed(self) -> bool: ...

    @property
    def value_policy(self) -> ExportValuePolicy | None: ...

    @property
    def allowed_values(self) -> tuple[str, ...] | None: ...


def validate_fixed_width_shape(field: _ExportField) -> None:
    """Refuse contradictory padding, justification, and sign declarations."""
    if field.length is None:
        return
    kind = str(getattr(field.kind, "value", field.kind))
    if kind == "filler":
        if field.signed:
            raise RegistryValidationError(f"filler export field {field.id!r} cannot declare signed")
        return
    expected = {
        ExportPadding.LEFT_ZERO: ExportJustification.RIGHT,
        ExportPadding.LEFT_SPACE: ExportJustification.RIGHT,
        ExportPadding.RIGHT_SPACE: ExportJustification.LEFT,
        ExportPadding.NONE: ExportJustification.NONE,
    }[field.padding]
    if field.justification is not expected:
        raise RegistryValidationError(
            f"export field {field.id!r} padding {field.padding.value!r} requires "
            f"justification {expected.value!r}",
        )
    if field.signed and field.data_type != "money":
        raise RegistryValidationError(
            f"export field {field.id!r} can declare signed only for money data",
        )
    if field.signed and field.length < 2:
        raise RegistryValidationError(f"signed export field {field.id!r} requires at least two bytes")
    if field.signed and (
        field.padding is not ExportPadding.LEFT_ZERO or field.justification is not ExportJustification.RIGHT
    ):
        raise RegistryValidationError(
            f"signed export field {field.id!r} requires left-zero padding and right justification",
        )


def render_fixed_width_export_field(field: _ExportField, value: object) -> str:
    """Render one semantic field value to its complete exact-width wire text."""
    if field.length is None:
        raise RegistryValidationError(f"export field {field.id!r} must declare length")
    kind = str(getattr(field.kind, "value", field.kind))
    if kind == "filler":
        return " " * field.length
    if kind == "literal":
        value = field.literal
    value = project_export_value(field.value_policy, value)
    _require_allowed_value(field, value)
    if field.data_type == "money":
        return _render_money(field, value)
    if field.data_type == "decimal":
        if field.decimals is None:
            raise RegistryValidationError(f"decimal export field {field.id!r} must declare decimals")
        return _render_scaled_numeric(field, value, scale=field.decimals)
    if field.data_type == "integer":
        return _render_integer(field, value)
    if field.data_type == "boolean":
        return _pad(field, _render_boolean(value))
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value
    else:
        raise RegistryValidationError(
            f"export field {field.id!r} {field.data_type!r} value must be text or absent",
        )
    return _pad(field, text)


def parse_fixed_width_export_field(field: _ExportField, raw: str) -> Decimal | str | bool | None:
    """Parse and validate one complete exact-width field from wire text."""
    if field.length is None:
        raise RegistryValidationError(f"export field {field.id!r} must declare length")
    if len(raw) != field.length:
        raise RegistryValidationError(
            f"export field {field.id!r} expected {field.length} wire characters, got {len(raw)}",
        )
    validate_export_wire_value(field.value_policy, raw)
    kind = str(getattr(field.kind, "value", field.kind))
    if kind == "filler":
        if raw != " " * field.length:
            raise RegistryValidationError(f"filler export field {field.id!r} contains non-space data")
        return None
    if kind == "literal":
        expected = render_fixed_width_export_field(field, field.literal)
        if raw != expected:
            raise RegistryValidationError(f"export literal field {field.id!r} does not match the registry layout")
        return field.literal
    parsed: Decimal | str | bool | None
    if field.data_type == "money":
        parsed = _parse_scaled_numeric(field, raw, scale=2)
    elif field.data_type == "decimal":
        if field.decimals is None:
            raise RegistryValidationError(f"decimal export field {field.id!r} must declare decimals")
        parsed = _parse_scaled_numeric(field, raw, scale=field.decimals)
    elif field.data_type == "integer":
        parsed = _parse_integer(field, raw)
    elif field.data_type == "boolean":
        text = _unpad(field, raw)
        if text == "":
            parsed = None
        elif text == "X":
            parsed = True
        else:
            raise RegistryValidationError("boolean export field must contain canonical X or blank wire data")
    else:
        text = _unpad(field, raw)
        parsed = text if text else None
    _require_allowed_value(field, parsed)
    if field.value_policy is None and render_fixed_width_export_field(field, parsed) != raw:
        raise RegistryValidationError(f"export field {field.id!r} contains noncanonical fixed-width data")
    return parsed


def pad_fixed_width_text(
    value: str,
    *,
    length: int,
    padding: ExportPadding,
    justification: ExportJustification,
) -> str:
    """Apply the canonical padding contract to already-rendered text."""
    if len(value) > length:
        raise RegistryValidationError(f"fixed-width value exceeds length {length}")
    if padding is ExportPadding.NONE:
        if justification is not ExportJustification.NONE:
            raise RegistryValidationError("no-padding fixed-width value requires no justification")
        return value.ljust(length, " ")
    if padding is ExportPadding.LEFT_ZERO:
        if justification is not ExportJustification.RIGHT:
            raise RegistryValidationError("left-zero padding requires right justification")
        return value.rjust(length, "0")
    if padding is ExportPadding.LEFT_SPACE:
        if justification is not ExportJustification.RIGHT:
            raise RegistryValidationError("left-space padding requires right justification")
        return value.rjust(length, " ")
    if justification is not ExportJustification.LEFT:
        raise RegistryValidationError("right-space padding requires left justification")
    return value.ljust(length, " ")


def _coerce_numeric(field: _ExportField, value: object) -> Decimal:
    try:
        return coerce_fixed_width_decimal(value)
    except ValueError as exc:
        raise RegistryValidationError(f"export field {field.id!r} has an invalid numeric value") from exc


def _require_allowed_value(field: _ExportField, value: object) -> None:
    if field.allowed_values is None:
        return
    number = _coerce_numeric(field, value)
    if number != number.to_integral_value():
        raise RegistryValidationError(f"export field {field.id!r} value is not an allowed integer")
    canonical = str(int(number))
    if canonical not in field.allowed_values:
        raise RegistryValidationError(
            f"export field {field.id!r} value {canonical!r} is outside allowed_values",
        )


def _render_integer(field: _ExportField, value: object) -> str:
    number = _coerce_numeric(field, value)
    if number != number.to_integral_value():
        raise RegistryValidationError(f"integer export field {field.id!r} cannot render a fractional value")
    return _render_numeric_digits(field, str(abs(int(number))), negative=number < 0)


def _render_scaled_numeric(field: _ExportField, value: object, *, scale: int) -> str:
    number = _coerce_numeric(field, value)
    scaled = (abs(number) * (Decimal(10) ** scale)).to_integral_value(rounding=ROUND_HALF_UP)
    return _render_numeric_digits(field, str(int(scaled)), negative=number < 0)


def _render_money(field: _ExportField, value: object) -> str:
    number = _coerce_numeric(field, value)
    scaled = round_to_cents(abs(number)) * 100
    return _render_numeric_digits(field, str(int(scaled)), negative=number < 0)


def _render_numeric_digits(field: _ExportField, digits: str, *, negative: bool) -> str:
    assert field.length is not None
    if negative and not field.signed:
        raise RegistryValidationError(f"unsigned export field {field.id!r} cannot render a negative value")
    if field.signed:
        magnitude_width = field.length - 1
        if len(digits) > magnitude_width:
            raise RegistryValidationError(f"export field {field.id!r} value exceeds length {field.length}")
        return ("N" if negative else " ") + digits.rjust(magnitude_width, "0")
    return _pad(field, digits)


def _parse_integer(field: _ExportField, raw: str) -> Decimal:
    negative, digits = _split_numeric_wire(field, raw)
    value = Decimal(int(digits))
    return -value if negative else value


def _parse_scaled_numeric(field: _ExportField, raw: str, *, scale: int) -> Decimal:
    negative, digits = _split_numeric_wire(field, raw)
    value = Decimal(int(digits)).scaleb(-scale)
    return -value if negative else value


def _split_numeric_wire(field: _ExportField, raw: str) -> tuple[bool, str]:
    if field.signed:
        marker, digits = raw[:1], raw[1:]
        if marker not in {"N", " "}:
            raise RegistryValidationError(
                f"signed export field {field.id!r} must use ASCII space or N as its sign marker",
            )
        negative = marker == "N"
    else:
        negative = False
        digits = _unpad(field, raw)
    if not digits or not digits.isascii() or not digits.isdigit():
        raise RegistryValidationError(f"numeric export field {field.id!r} must contain only ASCII digits")
    return negative, digits


def _render_boolean(value: object) -> str:
    if value is None or value is False:
        return ""
    if value is True:
        return "X"
    if isinstance(value, str):
        if value in {"", "false"}:
            return ""
        if value in {"X", "true"}:
            return "X"
    raise RegistryValidationError(
        "boolean export values must be bool, absent, empty, canonical X, or exact internal true/false",
    )


def _pad(field: _ExportField, value: str) -> str:
    assert field.length is not None
    try:
        return pad_fixed_width_text(
            value,
            length=field.length,
            padding=field.padding,
            justification=field.justification,
        )
    except RegistryValidationError as exc:
        raise RegistryValidationError(f"export field {field.id!r}: {exc}") from exc


def _unpad(field: _ExportField, raw: str) -> str:
    if field.padding is ExportPadding.NONE:
        return raw.rstrip(" ")
    if field.padding is ExportPadding.LEFT_ZERO:
        value = raw.lstrip("0")
        return value or "0"
    if field.padding is ExportPadding.LEFT_SPACE:
        return raw.lstrip(" ")
    return raw.rstrip(" ")


__all__ = [
    "ExportEncoding",
    "ExportEncodingValue",
    "ExportJustification",
    "ExportJustificationValue",
    "ExportPadding",
    "ExportPaddingValue",
    "pad_fixed_width_text",
    "parse_fixed_width_export_field",
    "render_fixed_width_export_field",
    "validate_fixed_width_shape",
]
