"""Canonical semantic-to-wire codec for registry fixed-width export fields."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Annotated, Protocol

from pydantic import BeforeValidator

from ....core.casilla_id import CasillaId
from ....core.decimal.fixed_width import coerce_fixed_width_decimal
from ....core.errors.hierarchy import CadrumoError
from ....core.money.rounding import round_to_cents
from .errors import RegistryValidationError
from .export_value_policy import (
    ExportValuePolicy,
    policy_defines_absent_slot,
    project_export_value,
    validate_export_wire_value,
)
from .schema_base import ZERO_PADDED_EXPORT_DATA_TYPES, CasillaDataType


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


class ExportSignPosition(StrEnum):
    """A sign byte an official design reserves ahead of an amount's magnitude.

    The general AEAT convention reserves nothing: an 'N' displaces the leading
    digit of a negative amount and a non-negative amount is digits throughout.
    Some designs instead subdivide an amount into a leading alphabetic SIGNO
    position and a numeric magnitude that "no irá precedido de signo alguno";
    the magnitude then owns every remaining byte, and the sign byte follows
    the design's own rule rather than the general one.
    """

    #: 'N' when the amount is below zero, otherwise a space ("En cualquier otro
    #: caso el contenido del campo será un espacio").
    BLANK_OR_N = "blank_or_n"
    #: The design fixes the direction ("se consignará siempre una 'N'"), so the
    #: value is a non-negative magnitude written after an 'N'; when there is
    #: nothing to declare the whole slot "se rellenará a ceros".
    N_UNLESS_ZERO = "n_unless_zero"


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
ExportSignPositionValue = (
    Annotated[
        ExportSignPosition,
        BeforeValidator(lambda value: _coerce_closed_axis(value, ExportSignPosition)),
    ]
    | None
)


class ExportField(Protocol):
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
    def data_type(self) -> CasillaDataType: ...

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
    def sign_position(self) -> ExportSignPosition | None: ...

    @property
    def value_policy(self) -> ExportValuePolicy | None: ...

    @property
    def allowed_values(self) -> tuple[str, ...] | None: ...

    @property
    def minimum_year(self) -> int | None: ...


class _ExportRecord(Protocol):
    """The registry-owned declaration shape needed by the record codec."""

    @property
    def id(self) -> str: ...

    @property
    def encoding(self) -> str: ...

    @property
    def fields(self) -> tuple[ExportField, ...]: ...


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


def validate_fixed_width_shape(field: ExportField) -> None:
    """Refuse contradictory padding, justification, and sign declarations."""
    if field.length is None:
        return
    kind = str(getattr(field.kind, "value", field.kind))
    if kind == "filler":
        if field.signed:
            raise RegistryValidationError(f"filler export field {field.id!r} cannot declare signed")
        if field.sign_position is not None:
            raise RegistryValidationError(f"filler export field {field.id!r} cannot declare sign_position")
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
    if field.sign_position is not None:
        _validate_sign_position(field)


def render_fixed_width_export_field(field: ExportField, value: object) -> str:
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
        rendered = render_absent_slot(field)
    else:
        value = project_export_value(field.value_policy, value)
        if _is_absent_slot(field, value):
            rendered = render_absent_slot(field)
        else:
            require_allowed_value(field, value)
            require_minimum_year(field, value)
            rendered = _render_typed_value(field, value)
    if not _is_absent_slot(field, value):
        validate_export_wire_value(field.value_policy, rendered)
    return rendered


def _render_record_field_bytes(
    record: _ExportRecord,
    field: ExportField,
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
    field: ExportField,
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

    This is the sole registry-owned record-byte producer. The outbound payload
    assembly owner appends record terminators while composing the final stream.
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


def _require_record_coordinates(field: ExportField, *, record_id: str) -> tuple[int, int]:
    if field.offset is None or field.length is None:
        raise FixedWidthRecordRenderError(
            field_id=field.id,
            reason="missing_coordinates",
            export_record_id=record_id,
            offset_declared=field.offset is not None,
            length_declared=field.length is not None,
        )
    return field.offset, field.length


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


def _validate_signed_shape(field: ExportField) -> None:
    """Refuse a signed declaration the fixed-width sign marker cannot carry."""
    length = require_length(field)
    if field.data_type != "money":
        raise RegistryValidationError(
            f"export field {field.id!r} can declare signed only for money data",
        )
    if length < 2:
        raise RegistryValidationError(f"signed export field {field.id!r} requires at least two bytes")
    if field.padding is not ExportPadding.LEFT_ZERO or field.justification is not ExportJustification.RIGHT:
        raise RegistryValidationError(
            f"signed export field {field.id!r} requires left-zero padding and right justification",
        )


def _validate_sign_position(field: ExportField) -> None:
    """Refuse a reserved sign byte on a slot that cannot carry one.

    ``BLANK_OR_N`` writes a negative amount, so it needs ``signed``;
    ``N_UNLESS_ZERO`` writes a magnitude whose direction the design fixes, so a
    negative value there would say the opposite of the constant 'N' and the
    field must stay unsigned to refuse it.
    """
    length = require_length(field)
    if field.data_type != "money":
        raise RegistryValidationError(f"export field {field.id!r} can declare sign_position only for money data")
    if length < 2:
        raise RegistryValidationError(f"sign_position export field {field.id!r} requires at least two bytes")
    if field.padding is not ExportPadding.LEFT_ZERO or field.justification is not ExportJustification.RIGHT:
        raise RegistryValidationError(
            f"sign_position export field {field.id!r} requires left-zero padding and right justification",
        )
    if field.value_policy is not None or field.allowed_values is not None:
        raise RegistryValidationError(
            f"sign_position export field {field.id!r} cannot also declare a value policy or allowed values",
        )
    required_signed = field.sign_position is ExportSignPosition.BLANK_OR_N
    if field.signed is not required_signed:
        raise RegistryValidationError(
            f"sign_position {field.sign_position!s} on export field {field.id!r} requires signed = "
            f"{str(required_signed).lower()}",
        )


def require_decimals(field: ExportField) -> int:
    if field.decimals is None:
        raise RegistryValidationError(f"decimal export field {field.id!r} must declare decimals")
    return field.decimals


def require_length(field: ExportField) -> int:
    """Return the field's declared byte length, refusing a slot that declares none."""
    if field.length is None:
        raise RegistryValidationError(f"export field {field.id!r} must declare length")
    return field.length


def _render_typed_value(field: ExportField, value: object) -> str:
    """Render one already-projected value under the field's declared data type."""
    if field.value_policy in {ExportValuePolicy.INTEGER_PART, ExportValuePolicy.SIGNED_COMPONENT_INTEGER_PART}:
        return _render_integer_part(field, value)
    if field.value_policy in {
        ExportValuePolicy.FRACTIONAL_DIGITS,
        ExportValuePolicy.SIGNED_COMPONENT_FRACTIONAL_DIGITS,
    }:
        return _render_fractional_digits(field, value)
    if field.data_type == "money":
        return _render_money(field, value)
    if field.data_type == "decimal":
        return _render_scaled_numeric(field, value, scale=require_decimals(field))
    if field.data_type == "integer":
        return _render_integer(field, value)
    if field.data_type == "boolean":
        return _pad(field, _render_boolean(value))
    return _pad(field, _render_text(field, value))


def _render_text(field: ExportField, value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    raise RegistryValidationError(
        f"export field {field.id!r} {str(field.data_type)!r} value must be text or absent",
    )


def _coerce_numeric(field: ExportField, value: object) -> Decimal:
    try:
        return coerce_fixed_width_decimal(value)
    except ValueError as exc:
        raise RegistryValidationError(f"export field {field.id!r} has an invalid numeric value") from exc


def require_minimum_year(field: ExportField, value: object) -> None:
    if field.minimum_year is None:
        return
    year = _coerce_numeric(field, value)
    if year < field.minimum_year:
        raise RegistryValidationError(
            f"export field {field.id!r} year is below its official minimum {field.minimum_year}",
        )


def require_allowed_value(field: ExportField, value: object) -> None:
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


def _is_absent_slot(field: ExportField, value: object) -> bool:
    """Report a field slot carrying no value once its policy has projected.

    Absence is tested after projection so a value policy that assigns its own
    meaning to an empty slot keeps it: an unselected checkbox projects to its
    declared ``0`` and arrives here as a value, not an absence.
    """
    return value is None or value == ""


def zero_fill_is_only_absence(field: ExportField) -> bool:
    """Whether a zero fill cannot carry a value under the field's declared domain or policy."""
    if field.allowed_values is not None and "0" not in field.allowed_values:
        return True
    if field.value_policy is None:
        return False
    try:
        validate_export_wire_value(field.value_policy, "0" * require_length(field))
    except RegistryValidationError:
        return True
    return False


def render_absent_slot(field: ExportField) -> str:
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
    if field.value_policy is ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN:
        # This source-backed sign slot prints 0 when its amount is absent. A
        # generic optional text fill would print a space and contradict the
        # signed-component wire policy before the record context guard runs.
        rendered = _render_typed_value(field, project_export_value(field.value_policy, 0))
        validate_export_wire_value(field.value_policy, rendered)
        return rendered
    if field.data_type in ZERO_PADDED_EXPORT_DATA_TYPES:
        return _render_numeric_digits(field, "", negative=False)
    return _pad(field, "")


def _render_integer(field: ExportField, value: object) -> str:
    number = _coerce_numeric(field, value)
    if number != number.to_integral_value():
        raise RegistryValidationError(f"integer export field {field.id!r} cannot render a fractional value")
    return _render_numeric_digits(field, str(abs(int(number))), negative=number < 0)


def _render_integer_part(field: ExportField, value: object) -> str:
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


def _render_fractional_digits(field: ExportField, value: object) -> str:
    """Render exactly the fractional digits this part's slot holds.

    Refuses rather than truncates when the quantity carries more precision than
    the slot represents. Dropping a digit here would under-declare a filed
    figure while leaving a structurally valid record behind, which is precisely
    the failure a fixed-width export must never produce silently.
    """
    length = require_length(field)
    number = _coerce_numeric(field, value)
    fraction = number - number.to_integral_value(rounding=ROUND_DOWN)
    scaled = fraction * (Decimal(10) ** length)
    if scaled != scaled.to_integral_value():
        raise RegistryValidationError(
            f"export field {field.id!r} cannot represent {length} fractional digits of a value carrying more precision",
        )
    return str(int(scaled)).rjust(length, "0")


def _render_scaled_numeric(field: ExportField, value: object, *, scale: int) -> str:
    number = _coerce_numeric(field, value)
    scaled = (abs(number) * (Decimal(10) ** scale)).to_integral_value(rounding=ROUND_HALF_UP)
    return _render_numeric_digits(field, str(int(scaled)), negative=number < 0)


def _render_money(field: ExportField, value: object) -> str:
    number = _coerce_numeric(field, value)
    scaled = round_to_cents(abs(number)) * 100
    return _render_numeric_digits(field, str(int(scaled)), negative=number < 0)


def _render_numeric_digits(field: ExportField, digits: str, *, negative: bool) -> str:
    length = require_length(field)
    if negative and not field.signed:
        raise RegistryValidationError(f"unsigned export field {field.id!r} cannot render a negative value")
    if field.sign_position is not None:
        return _render_with_reserved_sign(field, digits, negative=negative, length=length)
    if field.signed:
        return _render_signed_digits(field, digits, negative=negative, length=length)
    return _pad(field, digits)


def _render_with_reserved_sign(field: ExportField, digits: str, *, negative: bool, length: int) -> str:
    magnitude_width = length - 1
    if len(digits) > magnitude_width:
        raise RegistryValidationError(f"export field {field.id!r} value exceeds length {length}")
    magnitude = digits.rjust(magnitude_width, "0")
    if field.sign_position is ExportSignPosition.N_UNLESS_ZERO:
        return "0" * length if not digits.strip("0") else "N" + magnitude
    return ("N" if negative else " ") + magnitude


def _render_signed_digits(field: ExportField, digits: str, *, negative: bool, length: int) -> str:
    # AEAT states one convention for every diseno de registro, in "Disenos de
    # registro - breve manual de uso" v.2 (12/12/2022), CAT - Informatica
    # Tributaria:
    #
    #   "Todos los campos numericos se presentaran alineados a la derecha y
    #    rellenos a ceros por la izquierda, SIN SIGNOS y sin empaquetar."
    #   "Los campos numericos negativos se presentaran alineados a la derecha
    #    y rellenos a ceros por la izquierda, PRECEDIDOS DEL CARACTER 'N'."
    #
    # So the sign position is NOT reserved. A non-negative value fills the
    # whole slot with digits, and the 'N' DISPLACES the leading digit when the
    # value is negative -- which is why the corporate-tax design spells its
    # amounts "15 enteros (o N + 14) y 2 decimales" on a seventeen-byte slot.
    # "Sin signos" excludes a blank as much as a '+': a blank belongs to
    # alphanumeric and alphabetic fields, which pad with blancos, not to these.
    magnitude_width = length - 1 if negative else length
    if len(digits) > magnitude_width:
        raise RegistryValidationError(f"export field {field.id!r} value exceeds length {length}")
    return ("N" if negative else "") + digits.rjust(magnitude_width, "0")


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


def _pad(field: ExportField, value: str) -> str:
    length = require_length(field)
    try:
        return pad_fixed_width_text(
            value,
            length=length,
            padding=field.padding,
            justification=field.justification,
        )
    except RegistryValidationError as exc:
        raise RegistryValidationError(f"export field {field.id!r}: {exc}") from exc


__all__ = [
    "ExportEncoding",
    "ExportEncodingValue",
    "ExportJustification",
    "ExportJustificationValue",
    "ExportPadding",
    "ExportPaddingValue",
    "FixedWidthRecordRenderError",
    "pad_fixed_width_text",
    "render_fixed_width_export_field",
    "render_fixed_width_export_record_body",
    "validate_fixed_width_shape",
]
