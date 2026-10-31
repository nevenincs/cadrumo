"""A valid pending local filing receipt and its work unit, for filing-reader tests."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from ....core.period import Period
from ....domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    derive_filing_record_id,
)
from ....domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id


def filing_source(
    *, profile_id: UUID, calculation_revision_id: str, filed_by: str, now: datetime
) -> tuple[WorkUnit, ModeloRecord]:
    """Build a valid filing receipt whose profile and period match its unit."""
    period = Period.from_year_and_code(2026, "1T")
    unit_id = derive_work_unit_id(
        bucket_id=str(profile_id), modelo="303", filing_year=2026, period=period, revision_id="test-revision"
    )
    filing_id = derive_filing_record_id(
        work_unit_id=unit_id,
        calculation_revision_id=calculation_revision_id,
        filed_by=filed_by,
    )
    unit = WorkUnit(
        work_unit_id=unit_id,
        bucket_id=str(profile_id),
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="test-revision",
        name="First-quarter return",
        created_at=now,
        updated_at=now,
        state=WorkUnitState.BORRADOR,
        current_calculation_revision_id=calculation_revision_id,
        filed_calculation_revision_id=calculation_revision_id,
        current_filing_record_id=filing_id,
    )
    record = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=unit_id,
        calculation_revision_id=calculation_revision_id,
        bucket_id=str(profile_id),
        modelo="303",
        filing_year=2026,
        period=period,
        filed_at=now,
        filed_by=filed_by,
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
    )
    return unit, record
