"""Modelo 347 declarado casillas that belong to one counterparty's record."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...core.decimal.coercion import coerce_decimal
from ...domain.calculations.export_field_kind import CasillaFieldKind
from ...domain.calculations.registry.schema_exports import ExportRecordDefinition
from ...domain.filing.errors import FilingExportValidationError
from .export_refusal_doors import ExportRefusalReason, export_input_decision
from .record_types import RecordRenderRow

_M347_DECLARADO_RECORD_ID = "m347-declarado"
_NUMERIC_DATA_TYPES = frozenset({"money", "integer", "decimal"})


def require_m347_declarado_casillas_have_one_row(
    record: ExportRecordDefinition,
    *,
    rows: Sequence[RecordRenderRow],
    casilla_values: dict[CasillaId, object],
) -> None:
    """Refuse a single-valued casilla that the fichero would copy onto several declarado rows.

    Every type 2 declarado field belongs to the counterparty its record
    describes, but these casillas hold one value for the whole declaration and
    no binding names the counterparty it concerns. Writing the value on each row
    would state it for counterparties it was never typed for.
    """
    if record.id != _M347_DECLARADO_RECORD_ID or not rows[1:]:
        return
    populated = sorted(
        {
            str(field.casilla_id)
            for field in record.fields
            if field.kind == CasillaFieldKind.CASILLA
            and field.casilla_id is not None
            and _carries_value(casilla_values.get(field.casilla_id), numeric=field.data_type in _NUMERIC_DATA_TYPES)
        },
    )
    if populated:
        raise FilingExportValidationError(
            f"export record {record.id!r} has {len(rows)} counterparty rows but single-valued casillas "
            f"{', '.join(populated)} cannot be attributed to one of them",
            translated_message="application.filing.export.errors.counterparty_rows_unattributable",
            context={
                "record_id": record.id,
                "row_count": len(rows),
                "casilla_ids": tuple(populated),
                "casillas": ", ".join(populated),
            },
            precondition_verdict=export_input_decision(ExportRefusalReason.COUNTERPARTY_ROWS_UNATTRIBUTABLE),
        )


def _carries_value(value: object, *, numeric: bool) -> bool:
    if value is None or (isinstance(value, str) and not value.strip()):
        return False
    if numeric:
        # A proven zero fills a numeric slot with zeros on every row, as an absent value does.
        return coerce_decimal(value) != Decimal(0)
    return True
