"""Strict public result of a locally recorded Modelo work amendment."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, NonNegativeInt, model_validator

from ...core.identity.hex_ids import FilingRecordId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.modelos.calculation_revision_amendment import (
    CalculationRevisionAmendmentKind,
    M303RectificativaMotive,
)
from ...domain.modelos.filing_record import AeatConfirmationState, FilingOrigin
from .filing_projection import ModeloFilingRecordSnapshot


class ModeloWorkAmendPublicResultV2(BaseModel):
    """The writer's complete local record and its amendment handoff facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[2] = 2
    record: ModeloFilingRecordSnapshot
    source_filing_record_id: FilingRecordId
    amended_from_filing_record_id: FilingRecordId
    amendment_kind: CalculationRevisionAmendmentKind
    corrected_casilla_count: NonNegativeInt
    m303_rectificativa_motive: M303RectificativaMotive | None = None
    handoff_required: Literal[True] = True

    @property
    def filing_record_id(self) -> FilingRecordId:
        """Use the canonical record identity without a second wire field."""
        return self.record.filing_record_id

    @model_validator(mode="after")
    def _canonical_amendment(self) -> Self:
        if self.record.amends_filing_record_id != self.amended_from_filing_record_id:
            raise ValueError("amendment source must match the recorded source")
        if self.record.declaration_kind.value != self.amendment_kind.value:
            raise ValueError("amendment kind must match the recorded declaration")
        if (
            self.record.origin is not FilingOrigin.LOCAL
            or self.record.confirmation is not AeatConfirmationState.PENDIENTE
            or self.record.external_evidence is not None
        ):
            raise ValueError("amendment result must remain a pending local filing")
        return self
