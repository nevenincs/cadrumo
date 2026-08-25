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
    :class:`application.modelo._ports.FicheroBoeRecordRenderer`
        The structural port this class satisfies.
    :func:`domain.calculations.registry.render_fixed_width_export_field`
        The canonical exact-width field codec reused by this renderer.
"""

from __future__ import annotations

from collections.abc import Mapping

from .....core import CasillaId
from .....domain.calculations.registry.schema import ExportRecordDefinition
from .....domain.calculations.registry.fixed_width_codec import (
    FixedWidthRecordRenderError,
    render_fixed_width_export_record_body,
)
from .....domain.modelos import ModeloExportError


def _export_error(*, field_id: str | None, reason: str, **context: object) -> ModeloExportError:
    """Build the port's failure with the diagnosis its callers re-raise from.

    The sentence is resolved from the port error's own registered key; the
    producer's condition travels as the ``reason`` discriminant so the boundary
    forwards machine facts rather than a re-wrapped English string.
    """
    payload: dict[str, object] = {"reason": reason, **context}
    if field_id is not None:
        payload["export_field_id"] = field_id
    return ModeloExportError(translated_message="errors.fail.modelo_export", context=payload)


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
        try:
            return render_fixed_width_export_record_body(record, field_values=field_values)
        except FixedWidthRecordRenderError as exc:
            raise _export_error(
                field_id=exc.field_id,
                reason=exc.reason,
                export_record_id=exc.export_record_id,
            ) from exc


__all__ = ["RegistryFixedWidthRecordRenderer"]
