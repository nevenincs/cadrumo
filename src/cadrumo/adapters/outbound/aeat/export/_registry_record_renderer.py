"""Render a registry-declared fixed-width record into fichero-BOE bytes.

This is the bridge between the registry's declarative export layout
(:class:`domain.calculations.registry.ExportRecordDefinition`, which says
*what* each field is and where it sits) and the explicit-spec byte helpers in
:mod:`._formats` (which say *how* a field becomes bytes). It exists so an
application-layer caller can hand over a record declaration plus the values an
operator entered and receive wire bytes, without naming a single wire-format
type itself.

The translation is deliberately generic rather than modelo-specific: every
input it reads - field coordinates, ``kind``, ``data_type``, ``justification``,
``padding``, ``signed``, ``encoding`` - is a registry declaration, so any modelo
whose layout is fixed-width renders through the same path. Modelo 145 is the
first caller, not a special case.

Failures surface as :class:`domain.modelos.ModeloExportError` rather than the
adapter's own :class:`AeatExportFormatError`. The renderer sits behind an
application-declared port, and a port that leaked an adapter-owned error type
would force its callers to import the adapter to catch it - reintroducing the
coupling the port removes. The domain error carries the same diagnosis in its
``context``.

See Also:
    :class:`application.modelo.FicheroBoeRecordRenderer`
        The structural port this class satisfies.
    :func:`._formats.render_record_body`
        The explicit-spec encoder this class builds specs for.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Final, cast

from .....core import CasillaId
from .....core.decimal import coerce_decimal_strict
from .....domain.calculations.registry import CasillaFieldKind, ExportFieldDefinition, ExportRecordDefinition
from .....domain.modelos import ModeloExportError
from ._errors import AeatExportFormatError
from ._formats import (
    FicheroBoeEncoding,
    FieldKind,
    Justification,
    RecordFieldSpec,
    SignedMode,
    record_field,
    render_record_body,
)

#: Registry spellings that differ from the encoder's own vocabulary for the
#: same character set. Every other declared encoding is already a member.
_ENCODING_ALIASES: Final[Mapping[str, FicheroBoeEncoding]] = {"latin-1": "iso-8859-1"}


def _export_error(message: str, *, field_id: str | None, reason: str, **context: object) -> ModeloExportError:
    """Build the port's failure with the diagnosis its callers re-raise from."""
    payload: dict[str, object] = {"reason": reason, **context}
    if field_id is not None:
        payload["export_field_id"] = field_id
    return ModeloExportError(message, context=payload)


def _fichero_encoding(encoding: str) -> FicheroBoeEncoding:
    """Map a registry encoding spelling onto the encoder's vocabulary."""
    aliased = _ENCODING_ALIASES.get(encoding)
    if aliased is not None:
        return aliased
    # The registry declares `encoding` from the same closed set the encoder
    # accepts, so anything without an alias is already a valid member. A value
    # from outside that set is refused by render_record_body rather than
    # silently mis-encoding the payload.
    # CAST-RATIONALE-FICHERO-ENCODING: registry `encoding` is a plain str;
    # narrowing to the encoder's closed Literal here is safe because
    # render_record_body itself refuses any value outside that set.
    return cast(FicheroBoeEncoding, encoding)


def _ordered_fields(record: ExportRecordDefinition) -> tuple[ExportFieldDefinition, ...]:
    """Order fields by wire position, keeping unpositioned ones deterministic.

    An unpositioned field is a declaration error this renderer refuses, but it
    must sort somewhere first for the refusal to name it deterministically
    rather than depending on declaration order.
    """
    return tuple(
        sorted(record.fields, key=lambda field: (-1 if field.offset is None else field.offset, field.id)),
    )


def _require_coordinates(field: ExportFieldDefinition) -> tuple[int, int]:
    """Return the field's one-based offset and length, refusing a partial declaration."""
    if field.offset is None or field.length is None:
        raise _export_error(
            f"export field {field.id!r} lacks fixed-width coordinates",
            field_id=field.id,
            reason="missing_coordinates",
        )
    return field.offset, field.length


def _money_value(field: ExportFieldDefinition, raw: str) -> Decimal | None:
    """Parse a declared-money value, or ``None`` when the operator left it blank."""
    text = raw.strip()
    if not text:
        return None
    try:
        return coerce_decimal_strict(text)
    except (InvalidOperation, ValueError) as exc:
        raise _export_error(
            f"export field {field.id!r} has an invalid money value",
            field_id=field.id,
            reason="money_value",
        ) from exc


def _integer_text(field: ExportFieldDefinition, raw: str) -> str:
    """Normalise a declared-integer value, or empty when the operator left it blank."""
    text = raw.strip()
    if not text:
        return ""
    try:
        return str(int(text))
    except ValueError as exc:
        raise _export_error(
            f"export field {field.id!r} has an invalid integer value",
            field_id=field.id,
            reason="integer_value",
        ) from exc


class RegistryFixedWidthRecordRenderer:
    """Renders any fixed-width registry record; satisfies the modelo renderer port.

    Stateless, so one instance is safe to share across callers and threads.
    """

    def render_record_body(
        self,
        record: ExportRecordDefinition,
        *,
        field_values: Mapping[CasillaId, str],
    ) -> bytes:
        """Return the encoded body for ``record``, without a line terminator."""
        specs, headers, casilla_values = self._encoder_inputs(record, field_values)
        if not specs:
            raise _export_error(
                f"export record {record.id!r} declares no renderable fields",
                field_id=None,
                reason="empty_record",
                export_record_id=record.id,
            )
        total_length = max(spec.offset + spec.length - 1 for spec in specs)
        try:
            return render_record_body(
                casilla_values=casilla_values,
                headers=headers,
                specs=specs,
                encoding=_fichero_encoding(record.encoding),
                total_length=total_length,
            )
        except AeatExportFormatError as exc:
            raise _export_error(
                f"export record {record.id!r} could not be rendered: {exc}",
                field_id=None,
                reason="fixed_width_encoder",
                export_record_id=record.id,
            ) from exc

    def _encoder_inputs(
        self,
        record: ExportRecordDefinition,
        field_values: Mapping[CasillaId, str],
    ) -> tuple[tuple[RecordFieldSpec, ...], dict[str, str], dict[CasillaId, Decimal]]:
        """Translate one registry record into the encoder's spec/value inputs.

        Money casillas travel as parsed ``Decimal`` values keyed by casilla id;
        everything else travels as pre-rendered header text. That split is the
        encoder's contract, not a choice made here.
        """
        specs: list[RecordFieldSpec] = []
        headers: dict[str, str] = {}
        casilla_values: dict[CasillaId, Decimal] = {}

        for field in _ordered_fields(record):
            offset, length = _require_coordinates(field)
            justification = Justification.LEFT if field.justification == "left" else Justification.RIGHT
            pad_char = "0" if field.padding == "left_zero" else " "

            if field.kind is CasillaFieldKind.LITERAL:
                specs.append(
                    record_field(
                        offset=offset,
                        length=length,
                        field_id=field.id,
                        kind=FieldKind.RESERVED,
                        literal_value=field.literal or "",
                    ),
                )
                continue

            if field.kind is CasillaFieldKind.FILLER:
                headers[field.id] = ""
                specs.append(
                    record_field(
                        offset=offset,
                        length=length,
                        field_id=field.id,
                        kind=FieldKind.ALPHANUMERIC,
                        justification=justification,
                        pad_char=pad_char,
                    ),
                )
                continue

            if field.kind is not CasillaFieldKind.CASILLA or field.casilla_id is None:
                raise _export_error(
                    f"export field {field.id!r} cannot be mapped to the fixed-width encoder",
                    field_id=field.id,
                    reason="field_kind",
                )

            raw = field_values.get(field.casilla_id, "")
            specs.append(
                self._value_spec(
                    field,
                    offset=offset,
                    length=length,
                    raw=raw,
                    justification=justification,
                    pad_char=pad_char,
                    headers=headers,
                    casilla_values=casilla_values,
                ),
            )

        return tuple(specs), headers, casilla_values

    def _value_spec(
        self,
        field: ExportFieldDefinition,
        *,
        offset: int,
        length: int,
        raw: str,
        justification: Justification,
        pad_char: str,
        headers: dict[str, str],
        casilla_values: dict[CasillaId, Decimal],
    ) -> RecordFieldSpec:
        """Build one casilla field's spec, recording its value on the right channel."""
        assert field.casilla_id is not None

        if field.data_type == "money":
            money = _money_value(field, raw)
            if money is not None:
                casilla_values[field.casilla_id] = money
            return record_field(
                offset=offset,
                length=length,
                field_id=field.id,
                casilla_id=field.casilla_id,
                kind=FieldKind.CURRENCY,
                justification=justification,
                pad_char=pad_char,
                signed_mode=SignedMode.INLINE_SIGN if field.signed else SignedMode.UNSIGNED,
            )

        if field.data_type == "integer":
            headers[field.id] = _integer_text(field, raw)
            kind = FieldKind.NUMERIC
        elif field.data_type == "text":
            headers[field.id] = raw
            kind = FieldKind.ALPHANUMERIC
        else:
            raise _export_error(
                f"export field {field.id!r} uses unsupported data_type {field.data_type!r}",
                field_id=field.id,
                reason="data_type",
                data_type=field.data_type,
            )

        return record_field(
            offset=offset,
            length=length,
            field_id=field.id,
            kind=kind,
            justification=justification,
            pad_char=pad_char,
        )


__all__ = ["RegistryFixedWidthRecordRenderer"]
