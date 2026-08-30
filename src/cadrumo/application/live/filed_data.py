"""Filed-declaration register listing helpers for live AEAT workflows.

This module is the read-only selector boundary between the authenticated
Sede declaration register and the heavier capture pipeline. It works only
with :class:`~cadrumo.adapters.outbound.aeat.sede.Declaracion` register rows:
listing reports expose which AEAT artefact links are available, and selector
helpers narrow one in-memory register result by period, expediente id, and
caller limit before any artefact is downloaded.

The helpers do not authenticate, open browser sessions, persist observations,
or stamp filing records. Those effects belong to
:mod:`cadrumo.application.live.filed_data_capture` and
:mod:`cadrumo.application.live.filed_observation_persistence` after the
live-read gate and registry checks have run.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from ...adapters.outbound.aeat.sede.declarations_schema import Declaracion
from ...core.identity import AeatExpedienteId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from .errors import LiveApplicationInputError
from .remote_state_models import FiledDataCaptureFailureRow


class FiledDataListingRow(BaseModel):
    """One filed declaration row listed from AEAT without downloading artefacts."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    year: int
    period: Period
    expediente_id: AeatExpedienteId
    status: str
    presented_at: datetime
    has_submitted_file: bool
    has_declaration_copy: bool
    has_justificante: bool


class FiledDataListingReport(BaseModel):
    """Read-only filed-declaration listing report."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    year_from: int
    year_to: int
    row_count: int
    rows: tuple[FiledDataListingRow, ...]


class BulkFiledDataListingReport(BaseModel):
    """Read-only filed-declaration listing report across multiple modelos."""

    model_config = STRICT_FROZEN_CONFIG

    modelos: tuple[str, ...]
    year_from: int
    year_to: int
    row_count: int
    failed_count: int
    rows: tuple[FiledDataListingRow, ...]
    failures: tuple[FiledDataCaptureFailureRow, ...]


def select_declarations_for_capture(
    declarations: tuple[Declaracion, ...],
    *,
    period: Period | None = None,
    expediente_id: str | None = None,
    limit: int | None = None,
) -> tuple[Declaracion, ...]:
    """Select register :class:`~cadrumo.adapters.outbound.aeat.sede.Declaracion` rows.

    Selection is an in-memory filter over one already-read register result. It
    does not fetch AEAT artefacts or persist local evidence; the capture service
    performs those steps after the live-read gate.
    """
    selected = declarations
    if period is not None:
        selected = tuple(row for row in selected if row.period == period)
    if expediente_id is not None:
        selected = tuple(row for row in selected if row.expediente_id == expediente_id)
    if expediente_id is not None and not selected:
        raise LiveApplicationInputError(
            translated_message="live.errors.expediente_not_found",
            context={"expediente_id": str(expediente_id)},
        )
    if limit is not None:
        selected = selected[:limit]
    return selected


def filed_data_listing_row(declaration: Declaracion) -> FiledDataListingRow:
    """Return link-availability metadata for one AEAT declaration register item.

    Returns:
        A :class:`FiledDataListingRow` with archive, declaration-copy, and
        justificante link-availability flags for the declaration.
    """
    return FiledDataListingRow(
        modelo=declaration.modelo,
        year=declaration.ejercicio,
        period=declaration.period,
        expediente_id=declaration.expediente_id,
        status=declaration.estado,
        presented_at=declaration.presented_at,
        has_submitted_file=bool(declaration.archive_link_text),
        has_declaration_copy=bool(
            declaration.declaration_copy_link_text,
        ),
        has_justificante=bool(declaration.justificante_link_text),
    )


__all__ = [
    "BulkFiledDataListingReport",
    "FiledDataListingReport",
    "FiledDataListingRow",
    "filed_data_listing_row",
    "select_declarations_for_capture",
]
