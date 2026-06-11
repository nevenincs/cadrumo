"""Filed-declaration listing helpers for live AEAT workflows.

This module uses :class:`Declaracion` to list and select filed declarations.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from ...adapters.outbound.aeat.sede import Declaracion
from ...core import Period
from ._errors import LiveApplicationInputError


class FiledDataListingRow(BaseModel):
    """One filed declaration row listed from AEAT without downloading artefacts."""

    model_config = ConfigDict(frozen=True)

    modelo: str
    year: int
    period: Period
    expediente_id: str
    status: str
    presented_at: datetime
    has_submitted_file: bool
    has_declaration_copy: bool
    has_justificante: bool


class FiledDataListingReport(BaseModel):
    """Read-only filed-declaration listing report."""

    model_config = ConfigDict(frozen=True)

    modelo: str
    year_from: int
    year_to: int
    row_count: int
    rows: tuple[FiledDataListingRow, ...]


def select_declarations_for_capture(
    declarations: tuple[Declaracion, ...],
    *,
    period: Period | None = None,
    expediente_id: str | None = None,
    limit: int | None = None,
) -> tuple[Declaracion, ...]:
    """Select :class:`Declaracion` rows for capture from one register query."""
    selected = declarations
    if period is not None:
        selected = tuple(row for row in selected if row.period == period)
    if expediente_id is not None:
        selected = tuple(row for row in selected if row.expediente_id == expediente_id)
    if expediente_id is not None and not selected:
        raise LiveApplicationInputError(
            message=f"AEAT declaration register did not return expediente {expediente_id!r}",
            translated_message="live.errors.expediente_not_found",
            context={"expediente_id": str(expediente_id)},
        )
    if limit is not None:
        selected = selected[:limit]
    return selected


def filed_data_listing_row(declaration: Declaracion) -> FiledDataListingRow:
    """Return a :class:`FiledDataListingRow` for one AEAT declaration register item."""
    return FiledDataListingRow(
        modelo=declaration.modelo,
        year=declaration.ejercicio,
        period=declaration.period,
        expediente_id=declaration.expediente_id,
        status=declaration.estado,
        presented_at=declaration.presented_at,
        has_submitted_file=bool(declaration.archive_link_text and declaration.archive_cell_index is not None),
        has_declaration_copy=bool(
            declaration.declaration_copy_link_text and declaration.declaration_copy_cell_index is not None,
        ),
        has_justificante=bool(declaration.justificante_link_text and declaration.justificante_cell_index is not None),
    )


__all__ = [
    "FiledDataListingReport",
    "FiledDataListingRow",
    "filed_data_listing_row",
    "select_declarations_for_capture",
]
