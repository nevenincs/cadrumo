"""Strict wire projection for a canonical Modelo edit baseline."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from ...core.filing_year import FilingYear
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.identity.hex_ids import CalculationRevisionId, ModeloEditBaselineId, WorkUnitId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.calculations.registry.ids import RevisionId
from ...domain.modelos.codes import ModeloCode
from .edit_contract import ModeloEditCompatibilityTupleV1, ModeloEditMutationFamily
from .edit_models import (
    MAX_MODELO_EDIT_SURFACE_ENTRIES,
    ModeloEditBaselineV1,
    ModeloEditPermittedSurfaceEntryV1,
    ModeloEditSchemaIdentityV1,
)


class ModeloEditApplyBaselineV1(BaseModel):
    """Wire mirror of ModeloEditBaselineV1 with a plain-string modelo code.

    Every field of ModeloEditBaselineV1 except ``modelo`` already crosses an
    operation payload safely: Hex64Str, bounded Annotated str, Period and the
    permitted-surface union are all plain Pydantic shapes with no custom core
    schema. Only ``modelo: ModeloCode`` does - it is a str subclass that
    customises its Pydantic core schema, which the operations payload-graph
    gate refuses inside a registered request payload - so only that one field
    is mirrored here. ``to_baseline`` re-validates it through the real type.
    """

    model_config = STRICT_FROZEN_CONFIG

    compatibility: ModeloEditCompatibilityTupleV1
    bucket_id: BucketId
    modelo: Annotated[str, Field(min_length=3, max_length=3, pattern=r"^\d{3}$")]
    filing_year: FilingYear
    period_filing_year: FilingYear
    period_code: Annotated[str, Field(min_length=1, max_length=16)]
    work_unit_id: WorkUnitId
    work_unit_record_digest: ContentDigest
    calculation_head_digest: ContentDigest
    current_calculation_revision_id: CalculationRevisionId | None
    law_selected_revision_id: RevisionId
    schema_identity: ModeloEditSchemaIdentityV1
    schema_version: Annotated[int, Field(ge=1)]
    permitted_surface: Annotated[
        tuple[ModeloEditPermittedSurfaceEntryV1, ...], Field(max_length=MAX_MODELO_EDIT_SURFACE_ENTRIES)
    ]
    permitted_surface_digest: ContentDigest
    mutation_family: ModeloEditMutationFamily
    issued_at: datetime
    expires_at: datetime
    baseline_id: ModeloEditBaselineId

    def to_baseline(self) -> ModeloEditBaselineV1:
        """Translate back to the real, fully re-validated domain baseline.

        ``period`` is mirrored the same way as ``modelo``: ``Period`` is a
        core ``BaseModel`` that does not declare ``strict=True``, which the
        operations payload-graph gate also refuses, so the wire form carries
        its two source fields and reconstructs the real type here.
        """
        data = self.model_dump(mode="python")
        data["modelo"] = ModeloCode(data["modelo"])
        period_filing_year = data.pop("period_filing_year")
        period_code = data.pop("period_code")
        data["period"] = Period.from_year_and_code(period_filing_year, period_code)
        return ModeloEditBaselineV1.model_validate(data)

    @classmethod
    def from_baseline(cls, baseline: ModeloEditBaselineV1) -> ModeloEditApplyBaselineV1:
        """Mirror a domain baseline onto the wire form ``to_baseline`` reverses.

        Kept beside its inverse so the two directions cannot drift into
        disagreeing about which fields are mirrored: adding a field to the
        wire type without teaching this method is a validation error here, not
        a silently dropped coordinate.
        """
        data = baseline.model_dump(mode="python")
        period = data.pop("period")
        # The wire baseline does not restate the contract version: the enclosing
        # ModeloEditApplySubmissionV1 already carries it, and declaring it twice
        # would let the two disagree.
        data.pop("edit_contract_version", None)
        data["modelo"] = str(baseline.modelo)
        data["period_filing_year"] = period["filing_year"]
        data["period_code"] = period["code"]
        return cls.model_validate(data)
