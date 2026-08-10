"""Render a registry-declared fixed-width record into fichero-BOE bytes.

This is the bridge between the registry's declarative export layout
(:class:`domain.calculations.registry.ExportRecordDefinition`, which says
*what* each field is and where it sits) and the public registry fixed-width
codec (which says *how* a field becomes bytes). It exists so an
application-layer caller can hand over a record declaration plus the values an
operator entered and receive wire bytes, without naming a single wire-format
type itself.

The translation is deliberately generic rather than modelo-specific: every
input it reads - field coordinates, ``kind``, ``data_type``, ``justification``,
``padding``, ``signed``, ``encoding`` - is a registry declaration, so any modelo
whose layout is fixed-width renders through the same path. Modelo 145 is the
first caller, not a special case.

Failures surface as :class:`domain.modelos.ModeloExportError`. The renderer sits behind an
application-declared port, and a port that leaked an adapter-owned error type
would force its callers to import the adapter to catch it - reintroducing the
coupling the port removes. The domain error carries the same diagnosis in its
``context``.

See Also:
    :class:`application.modelo.FicheroBoeRecordRenderer`
        The structural port this class satisfies.
    :func:`domain.calculations.registry.render_fixed_width_export_field`
        The canonical exact-width field codec reused by this renderer.
"""

from __future__ import annotations

from collections.abc import Mapping

from .....core import CasillaId
from .....domain.calculations.registry import (
    CasillaFieldKind,
    ExportFieldDefinition,
    ExportRecordDefinition,
    RegistryValidationError,
    render_fixed_width_export_field,
)
from .....domain.modelos import ModeloExportError


def _export_error(message: str, *, field_id: str | None, reason: str, **context: object) -> ModeloExportError:
    """Build the port's failure with the diagnosis its callers re-raise from."""
    payload: dict[str, object] = {"reason": reason, **context}
    if field_id is not None:
        payload["export_field_id"] = field_id
    return ModeloExportError(message, context=payload)


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
        fields = _ordered_fields(record)
        if not fields:
            raise _export_error(
                f"export record {record.id!r} declares no renderable fields",
                field_id=None,
                reason="empty_record",
                export_record_id=record.id,
            )
        total_length = max(offset + length - 1 for field in fields for offset, length in (_require_coordinates(field),))
        buffer = bytearray(b" " * total_length)
        occupied = bytearray(total_length)
        encoding = record.encoding
        for field in fields:
            offset, length = _require_coordinates(field)
            if field.kind not in {CasillaFieldKind.LITERAL, CasillaFieldKind.FILLER, CasillaFieldKind.CASILLA}:
                raise _export_error(
                    f"export field {field.id!r} cannot be mapped to the fixed-width renderer",
                    field_id=field.id,
                    reason="field_kind",
                )
            try:
                raw_value = field_values.get(field.casilla_id, "") if field.casilla_id is not None else ""
                rendered = render_fixed_width_export_field(field, raw_value).encode(encoding)
            except (LookupError, UnicodeError, RegistryValidationError) as exc:
                raise _export_error(
                    f"export field {field.id!r} has an invalid fixed-width value",
                    field_id=field.id,
                    reason="fixed_width_value",
                ) from exc
            if len(rendered) != length:
                raise _export_error(
                    f"export field {field.id!r} encoded to {len(rendered)} bytes instead of {length}",
                    field_id=field.id,
                    reason="encoded_width",
                )
            start = offset - 1
            end = start + length
            if any(occupied[start:end]):
                raise _export_error(
                    f"export field {field.id!r} overlaps another field",
                    field_id=field.id,
                    reason="overlap",
                )
            buffer[start:end] = rendered
            occupied[start:end] = b"\x01" * length
        return bytes(buffer)


__all__ = ["RegistryFixedWidthRecordRenderer"]
