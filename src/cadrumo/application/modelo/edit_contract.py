"""The publicly consumable face of the Modelo Edit Contract V1.

This module carries only what a package OUTSIDE ``application.modelo``
legitimately holds: the safe result receipt a guarded compare-and-swap
produces, the closed mutation family it names, the execution effect the
receipt records, and the fail-closed boundary posture all three share.

The rest of the Edit Contract V1 record family -- admission, parsing,
preflight, intents, addresses, refusals and capability projection -- stays
package-internal in ``_edit_models``, because no consumer outside the
package addresses those and publishing them would widen the contract to
the shape of its implementation rather than the shape of its use.

The dependency runs one way: ``_edit_models`` imports from here. The
internal record family references the receipt and the effect, so the
reverse direction would be a cycle.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from ...core.identity import (
    CalculationRevisionId,
    ContentDigest,
    ModeloEditBaselineId,
    ModeloEditMutationResultReceiptId,
    WorkUnitId,
)
from ...core.time.utc import validate_utc_aware
from ...domain.buckets.event import BucketEventId
from ..operations.models import OperationDefinitionId, OperationId, OperationReference
from ..operations.registry import OperationSchemaIdentityV1


class EditModel(BaseModel):
    """The common fail-closed boundary posture for Edit Contract V1 records."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)


class ModeloEditMutationFamily(StrEnum):
    """The closed set of edit-executed effects this V1 contract covers."""

    CALCULATE = "calculate"
    RECALCULATE = "recalculate"


class ModeloEditExecutionEffect(StrEnum):
    """The two possible outcomes of one guarded compare-and-swap execution."""

    UPDATED = "updated"
    NONE = "none"


class ModeloEditMutationResultReceiptV1(EditModel):
    """The safe domain proof co-committed with one guarded compare-and-swap edit.

    Carries no financial value, raw input, row content, or input digest. A
    matching receipt proves ``UPDATED``; a proven failed compare-and-swap
    proves ``NONE``.

    ``bucket_event_id`` is ``None`` on a duplicate-result confirmation: an
    identical content-addressed revision already exists, so this commit
    advances or confirms only the work-unit pointer and emits no fresh
    ``MODELO_CALCULATION_CREATED`` event to reference. It is always present
    when the commit created the revision.
    """

    receipt_id: ModeloEditMutationResultReceiptId
    operation_id: OperationId
    mutation_family: ModeloEditMutationFamily
    baseline_id: ModeloEditBaselineId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    bucket_event_id: BucketEventId | None
    effect: Literal[ModeloEditExecutionEffect.UPDATED] = ModeloEditExecutionEffect.UPDATED
    committed_at: datetime
    result_destination: OperationReference

    @model_validator(mode="after")
    def _require_utc_commit_time(self) -> ModeloEditMutationResultReceiptV1:
        validate_utc_aware(self.committed_at)
        return self


class ModeloEditCompatibilityTupleV1(EditModel):
    """Every distinct current-only version and digest axis this edit binds to.

    No member is collapsed into a generic shared ``version``, and a manifest
    version never substitutes for a definition or contract-set digest.
    """

    workspace_contract_version: Literal[1] = 1
    edit_contract_version: Literal[1] = 1
    operation_manifest_version: Literal[1] = 1
    contract_set_digest: ContentDigest
    operation_definition_id: OperationDefinitionId
    definition_contract_digest: ContentDigest
    request_schema: OperationSchemaIdentityV1
    result_schema: OperationSchemaIdentityV1
    observation_contract_version: Literal[1] = 1
    review_projection_contract_version: Literal[1] | None
    review_schema: OperationSchemaIdentityV1 | None
    workspace_refresh_target_version: Literal[1] = 1
    workspace_refresh_target_schema: OperationSchemaIdentityV1
    financial_operand_protocol_version: Literal[1] = 1
    financial_operand_schema: OperationSchemaIdentityV1

    @model_validator(mode="after")
    def _require_consistent_review_declaration(self) -> ModeloEditCompatibilityTupleV1:
        has_version = self.review_projection_contract_version is not None
        has_schema = self.review_schema is not None
        if has_version != has_schema:
            raise ValueError("edit compatibility REVIEW axis must declare version and schema together or neither")
        return self


__all__ = [
    "ModeloEditCompatibilityTupleV1",
    "ModeloEditExecutionEffect",
    "ModeloEditMutationFamily",
    "ModeloEditMutationResultReceiptV1",
]
