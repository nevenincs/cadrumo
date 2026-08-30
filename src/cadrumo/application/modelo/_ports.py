"""Structural ports for modelo record work the application layer does not own.

The application layer decides *which* record to render and *when*; it does not
own the AEAT wire format that record is rendered into. Fixed-width fichero-BOE
assembly is an outbound adapter concern, so the modelo services declare the
shape they need here and consume whatever satisfies it, rather than importing
:mod:`adapters.outbound.aeat.export` and pulling a wire format into an
application-layer module.

The ports are structural, following the same pattern as
:mod:`application.calculations._ports`: a concrete renderer satisfies
:class:`FicheroBoeRecordRenderer` by shape alone, so the implementation stays
adapter-owned and neither layer needs to import the other's module to make the
contract hold.

See Also:
    :class:`domain.calculations.registry.ExportRecordDefinition`
        Registry declaration of one fixed-width record, carrying the field
        coordinates, encoding, and line ending a renderer works from.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.schema_exports import ExportRecordDefinition


@runtime_checkable
class FicheroBoeRecordRenderer(Protocol):
    """Renders one registry-declared fixed-width record into its body bytes.

    The renderer owns the whole translation from registry declaration to wire
    bytes: field coordinates, justification and padding, the money/integer/text
    encodings, and the character set named by ``record.encoding``. Callers pass
    the operator-entered values as text exactly as they were captured, because
    deciding how a declared ``data_type`` becomes bytes is the wire format's
    judgement, not the caller's.

    The returned body carries no line terminator. Terminator ownership stays
    with the caller, which knows whether it is writing a lone record or one
    row of a larger file, and the registry declares the terminator separately
    on ``record.line_ending``.

    Implementations raise :class:`~ModeloExportError` when the
    record cannot be rendered - a field missing its fixed-width coordinates, a
    value that does not parse as its declared ``data_type``, or a rendered body
    whose length contradicts the declaration. The error's ``context`` names the
    offending ``export_field_id`` and a machine-readable ``reason`` so callers
    can re-raise in their own vocabulary without re-deriving the cause.
    """

    def render_record_body(
        self,
        record: ExportRecordDefinition,
        *,
        field_values: Mapping[CasillaId, str],
    ) -> bytes:
        """Return the fixed-width body for ``record`` filled from ``field_values``.

        Args:
            record: Registry declaration of the record to render.
            field_values: Operator-entered values keyed by casilla id, as text.
                A casilla the record declares but this mapping omits renders as
                its declared empty form rather than failing.

        Returns:
            The encoded record body, without a line terminator.
        """
        ...


__all__ = ["FicheroBoeRecordRenderer"]
