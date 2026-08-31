"""Canonical semantic-to-wire codec for registry fixed-width export fields."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Annotated, Literal, Protocol

from pydantic import BeforeValidator

from ....core.casilla_id import CasillaId
from ....core.decimal._fixed_width import coerce_fixed_width_decimal
from ....core.errors.hierarchy import CadrumoError
from ....core.money.rounding import round_to_cents
from .errors import RegistryValidationError
from .export_value_policy import (
    ExportValuePolicy,
    ParsedExportPolicyValue,
    normalize_parsed_export_policy_value,
    policy_defines_absent_slot,
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
    def offset(self) -> int | None: ...

    @property
    def casilla_id(self) -> CasillaId | None: ...

    @property
    def length(self) -> int | None: ...

    @property
    def kind(self) -> object: ...

    @property
    def literal(self) -> str | None: ...

    @property
    def data_type(self) -> Literal["text", "integer", "decimal", "money", "date", "boolean"]: ...

    @property
    def required(self) -> bool: ...

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


class _ExportRecord(Protocol):
    """The registry-owned declaration shape needed by the record codec."""

    @property
    def id(self) -> str: ...

    @property
    def encoding(self) -> str: ...

    @property
    def line_ending(self) -> Literal["crlf", "lf", "none"]: ...

    @property
    def fields(self) -> tuple[_ExportField, ...]: ...


class FixedWidthRecordRenderError(CadrumoError):
    """A registry-owned fixed-record rendering refusal with exact context.

    The condition travels as the ``reason`` discriminant plus the coordinates
    that produced it; the operator-facing sentence is resolved from the
    registered key, so no raise site authors English prose.
    """

    def __init__(
        self,
        *,
        field_id: str | None,
        reason: str,
        export_record_id: str,
        **facts: object,
    ) -> None:
        """Initialise the structured refusal with its registry coordinates."""
        context: dict[str, object] = {
            "reason": reason,
            "export_record_id": export_record_id,
            **facts,
        }
        if field_id is not None:
            context["export_field_id"] = field_id
        super().__init__(
            translated_message="errors.fail.fixed_width_record_render",
            context=context,
        )
        self.field_id = field_id
        self.reason = reason
        self.export_record_id = export_record_id


_LINE_ENDINGS: Mapping[str, bytes] = {"none": b"", "lf": b"\n", "crlf": b"\r\n"}


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
            f"export field {field.id!r} padding {field.padding.value!r} requires justification {expected.value!r}",
        )
    if field.signed:
        _validate_signed_shape(field)


def render_fixed_width_export_field(field: _ExportField, value: object) -> str:
    """Render one semantic field value to its complete exact-width wire text."""
    if field.length is None:
        raise RegistryValidationError(f"export field {field.id!r} must declare length")
    kind = str(getattr(field.kind, "value", field.kind))
    if kind == "filler":
        return " " * field.length
    if kind == "literal":
        value = field.literal
        # ``""`` is a declared literal payload, not a missing producer value.
        # It occurs in official fixed-width designs for an intentionally blank
        # slot.  Preserve that semantic distinction before generic absence
        # handling: a required casilla or header with no value must still
        # refuse, whereas this source-owned literal occupies its full slot
        # under the declaration's padding rule.
        if value == "":
            return _pad(field, value)
    if _is_absent_slot(field, value) and not policy_defines_absent_slot(field.value_policy):
        # Absence is settled BEFORE projection for every policy that does not
        # claim the empty slot. Every projector refuses ``None`` -- correctly, an
        # absent quantity is not a quantity -- so testing absence only after
        # projection made the blank fill unreachable on any field declaring a
        # policy, and an optional casilla the taxpayer legitimately lacks could
        # not be exported at all. The post-projection test below is kept for a
        # policy that projects an empty slot through to an empty value.
        rendered = _render_absent_slot(field)
    else:
        value = project_export_value(field.value_policy, value)
        if _is_absent_slot(field, value):
            rendered = _render_absent_slot(field)
        else:
            _require_allowed_value(field, value)
            rendered = _render_typed_value(field, value)
    if not _is_absent_slot(field, value):
        validate_export_wire_value(field.value_policy, rendered)
    return rendered


def _render_record_field_bytes(
    record: _ExportRecord,
    field: _ExportField,
    *,
    field_values: Mapping[CasillaId, str | None],
) -> bytes:
    kind = str(getattr(field.kind, "value", field.kind))
    if kind not in {"literal", "filler", "casilla"}:
        raise FixedWidthRecordRenderError(
            field_id=field.id,
            reason="field_kind",
            export_record_id=record.id,
            export_field_kind=kind,
        )
    try:
        raw_value = field_values.get(field.casilla_id) if field.casilla_id is not None else None
        return render_fixed_width_export_field(field, raw_value).encode(record.encoding)
    except (LookupError, UnicodeError, RegistryValidationError) as exc:
        raise FixedWidthRecordRenderError(
            field_id=field.id,
            reason="fixed_width_value",
            export_record_id=record.id,
            producer_error_type=type(exc).__name__,
        ) from exc


def _place_record_field_bytes(
    buffer: bytearray,
    occupied: bytearray,
    field: _ExportField,
    *,
    offset: int,
    length: int,
    rendered: bytes,
    record_id: str,
) -> None:
    if len(rendered) != length:
        raise FixedWidthRecordRenderError(
            field_id=field.id,
            reason="encoded_width",
            export_record_id=record_id,
            encoded_byte_count=len(rendered),
            declared_byte_count=length,
        )
    start = offset - 1
    end = start + length
    if any(occupied[start:end]):
        raise FixedWidthRecordRenderError(
            field_id=field.id,
            reason="overlap",
            export_record_id=record_id,
            declared_offset=offset,
            declared_byte_count=length,
        )
    buffer[start:end] = rendered
    occupied[start:end] = b"\x01" * length


def render_fixed_width_export_record_body(
    record: _ExportRecord,
    *,
    field_values: Mapping[CasillaId, str | None],
) -> bytes:
    """Render one registry-owned fixed-width record without its terminator.

    This is the sole record-byte producer. Callers that compose a multi-record
    payload must use :func:`render_fixed_width_export_record_payload` so the
    declared line ending remains part of the exact emitted member bytes.
    """
    fields = tuple(sorted(record.fields, key=lambda field: (-1 if field.offset is None else field.offset, field.id)))
    if not fields:
        raise FixedWidthRecordRenderError(
            field_id=None,
            reason="empty_record",
            export_record_id=record.id,
            renderable_field_count=0,
        )
    coordinates = tuple(_require_record_coordinates(field, record_id=record.id) for field in fields)
    total_length = max(offset + length - 1 for offset, length in coordinates)
    buffer = bytearray(b" " * total_length)
    occupied = bytearray(total_length)
    for field, (offset, length) in zip(fields, coordinates, strict=True):
        rendered = _render_record_field_bytes(record, field, field_values=field_values)
        _place_record_field_bytes(
            buffer,
            occupied,
            field,
            offset=offset,
            length=length,
            rendered=rendered,
            record_id=record.id,
        )
    return bytes(buffer)


def render_fixed_width_export_record_payload(
    record: _ExportRecord,
    *,
    field_values: Mapping[CasillaId, str | None],
) -> bytes:
    """Render one registry-owned record with its declared line terminator."""
    return render_fixed_width_export_record_body(record, field_values=field_values) + _LINE_ENDINGS[record.line_ending]


def _require_record_coordinates(field: _ExportField, *, record_id: str) -> tuple[int, int]:
    if field.offset is None or field.length is None:
        raise FixedWidthRecordRenderError(
            field_id=field.id,
            reason="missing_coordinates",
            export_record_id=record_id,
            offset_declared=field.offset is not None,
            length_declared=field.length is not None,
        )
    return field.offset, field.length


def parse_fixed_width_export_field(
    field: _ExportField,
    raw: str,
) -> ParsedExportPolicyValue:
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
    parsed: ParsedExportPolicyValue = _parse_typed_value(field, raw)
    _require_allowed_value(field, parsed)
    parsed = normalize_parsed_export_policy_value(field.value_policy, raw, parsed)
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


def _validate_signed_shape(field: _ExportField) -> None:
    """Refuse a signed declaration the fixed-width sign marker cannot carry."""
    assert field.length is not None
    if field.data_type != "money":
        raise RegistryValidationError(
            f"export field {field.id!r} can declare signed only for money data",
        )
    if field.length < 2:
        raise RegistryValidationError(f"signed export field {field.id!r} requires at least two bytes")
    if field.padding is not ExportPadding.LEFT_ZERO or field.justification is not ExportJustification.RIGHT:
        raise RegistryValidationError(
            f"signed export field {field.id!r} requires left-zero padding and right justification",
        )


def _require_decimals(field: _ExportField) -> int:
    if field.decimals is None:
        raise RegistryValidationError(f"decimal export field {field.id!r} must declare decimals")
    return field.decimals


def _render_typed_value(field: _ExportField, value: object) -> str:
    """Render one already-projected value under the field's declared data type."""
    if field.value_policy is ExportValuePolicy.INTEGER_PART:
        return _render_integer_part(field, value)
    if field.value_policy is ExportValuePolicy.FRACTIONAL_DIGITS:
        return _render_fractional_digits(field, value)
    if field.data_type == "money":
        return _render_money(field, value)
    if field.data_type == "decimal":
        return _render_scaled_numeric(field, value, scale=_require_decimals(field))
    if field.data_type == "integer":
        return _render_integer(field, value)
    if field.data_type == "boolean":
        return _pad(field, _render_boolean(value))
    return _pad(field, _render_text(field, value))


def _parse_typed_value(field: _ExportField, raw: str) -> ParsedExportPolicyValue:
    """Parse one padded wire value under the field's declared data type."""
    if field.data_type == "money":
        return _parse_scaled_numeric(field, raw, scale=2)
    if field.data_type == "decimal":
        return _parse_scaled_numeric(field, raw, scale=_require_decimals(field))
    if field.data_type == "integer":
        return _parse_integer(field, raw)
    if field.data_type == "boolean":
        return _parse_boolean(field, raw)
    text = _unpad(field, raw)
    return text if text else None


def _render_text(field: _ExportField, value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    raise RegistryValidationError(
        f"export field {field.id!r} {field.data_type!r} value must be text or absent",
    )


def _parse_boolean(field: _ExportField, raw: str) -> bool | None:
    text = _unpad(field, raw)
    if text == "":
        return None
    if text == "X":
        return True
    raise RegistryValidationError("boolean export field must contain canonical X or blank wire data")


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


_NUMERIC_DATA_TYPES = frozenset({"integer", "decimal", "money"})


def _is_absent_slot(field: _ExportField, value: object) -> bool:
    """Report a field slot carrying no value once its policy has projected.

    Absence is tested after projection so a value policy that assigns its own
    meaning to an empty slot keeps it: an unselected checkbox projects to its
    declared ``0`` and arrives here as a value, not an absence.
    """
    return value is None or value == ""


def _render_absent_slot(field: _ExportField) -> str:
    """Render an empty optional slot as its declared width-correct blank fill.

    A fixed-width record gives every field its byte slot unconditionally, so an
    optional casilla the taxpayer legitimately lacks -- the birth year of a
    descendant they do not have, or a regimen activity the authority cannot
    identify -- still has to occupy its width. AEAT's record designs fill absent
    numeric fields with zeros ("los campos numéricos que no tengan contenido se
    rellenarán a ceros") and text fields with their declared space padding. The
    fill is therefore read from the registry declaration rather than chosen
    upstream, and absence is never turned into a semantic value.

    A field the layout declares ``required`` has no blank representation and
    refuses instead, so an omitted mandatory figure cannot reach the wire as a
    zero.
    """
    if field.required:
        raise RegistryValidationError(
            f"required export field {field.id!r} has no value to render",
        )
    if field.data_type in _NUMERIC_DATA_TYPES:
        return _render_numeric_digits(field, "", negative=False)
    return _pad(field, "")


def _render_integer(field: _ExportField, value: object) -> str:
    number = _coerce_numeric(field, value)
    if number != number.to_integral_value():
        raise RegistryValidationError(f"integer export field {field.id!r} cannot render a fractional value")
    return _render_numeric_digits(field, str(abs(int(number))), negative=number < 0)


def _render_integer_part(field: _ExportField, value: object) -> str:
    """Render the integer component of a quantity AEAT prints as a split pair.

    Dispatched ahead of the data-type table because the part's representation is
    settled entirely by its policy and its own slot width: the fractional digits
    live in the sibling field, so scaling this one by the field's ``decimals``
    would write the whole quantity into the half that carries none of it.
    """
    number = _coerce_numeric(field, value)
    return _render_numeric_digits(
        field,
        str(int(number.to_integral_value(rounding=ROUND_DOWN))),
        negative=False,
    )


def _render_fractional_digits(field: _ExportField, value: object) -> str:
    """Render exactly the fractional digits this part's slot holds.

    Refuses rather than truncates when the quantity carries more precision than
    the slot represents. Dropping a digit here would under-declare a filed
    figure while leaving a structurally valid record behind, which is precisely
    the failure a fixed-width export must never produce silently.
    """
    assert field.length is not None
    number = _coerce_numeric(field, value)
    fraction = number - number.to_integral_value(rounding=ROUND_DOWN)
    scaled = fraction * (Decimal(10) ** field.length)
    if scaled != scaled.to_integral_value():
        raise RegistryValidationError(
            f"export field {field.id!r} cannot represent {field.length} fractional digits "
            f"of a value carrying more precision",
        )
    return str(int(scaled)).rjust(field.length, "0")


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
    "FixedWidthRecordRenderError",
    "pad_fixed_width_text",
    "parse_fixed_width_export_field",
    "render_fixed_width_export_field",
    "render_fixed_width_export_record_body",
    "render_fixed_width_export_record_payload",
    "validate_fixed_width_shape",
]
