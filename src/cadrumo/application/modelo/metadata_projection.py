"""Strict snapshots of canonical work-unit metadata for private operation results."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator

from ...core.filing_year import FilingYear
from ...core.hex import Hex64Str
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.ids import RevisionId
from ...domain.contribuyente.ccaa import CCAA
from ...domain.modelos.filing_text import ModeloActorLabel, OperatorReason
from ...domain.modelos.work_unit import WorkUnit, WorkUnitState
from ..operations.public_period import PublicPeriod


class ModeloWorkMetadataSnapshot(BaseModel):
    """One observed or committed unit, excluding calculation and filing payloads."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    work_unit_id: WorkUnitId
    bucket_id: BucketId
    modelo: Annotated[str, Field(min_length=1, max_length=16)]
    filing_year: FilingYear
    period: PublicPeriod
    revision_id: RevisionId
    name: Annotated[str, Field(min_length=1, max_length=200)]
    created_at: datetime
    updated_at: datetime
    state: WorkUnitState
    discarded_at: datetime | None
    discarded_by: ModeloActorLabel | None
    discard_reason: OperatorReason | None
    current_calculation_revision_id: Hex64Str | None
    filed_calculation_revision_id: Hex64Str | None
    current_filing_record_id: Hex64Str | None
    causante_ccaa: Annotated[str, Field(min_length=1, max_length=64)] | None

    @classmethod
    def from_work_unit(cls, unit: WorkUnit) -> Self:
        """Project only the canonical writer or reader's immutable return value."""
        return cls.model_validate(
            unit.model_dump(mode="python")
            | {
                "modelo": str(unit.modelo),
                "period": PublicPeriod.from_period(unit.period),
                "causante_ccaa": unit.causante_ccaa.value if unit.causante_ccaa is not None else None,
            }
        )

    def to_work_unit(self) -> WorkUnit:
        """Restore the domain value for existing rendering without reading storage."""
        return WorkUnit.model_validate(
            self.model_dump(mode="python")
            | {
                "period": self.period.to_period(),
                "causante_ccaa": CCAA(self.causante_ccaa) if self.causante_ccaa is not None else None,
            }
        )

    @model_validator(mode="after")
    def _canonical_unit(self) -> Self:
        self.to_work_unit()
        return self
