"""Shared coordinates for the registered executor conformance outcome assertions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from .registered_executor_case_support import (
    _resolve_result_projection,
)


@dataclass(frozen=True)
class ExecutorOutcome:
    """Executed operation coordinates and fixtures shared by every outcome assertion."""

    asset_before: Any
    asset_repository: Any
    attachment_case: Any
    bienes_before: Any
    bulk_classify_before: Any
    case: Any
    cleanup: Any
    certificate_state_before: Any
    definition_id: Any
    definition: Any
    driver: Any
    evidence_case: Any
    family_preparation: Any
    followup_case: Any
    inventory_before: Any
    inventory_repository: Any
    invoice_catalogue_before: Any
    iva_history_before: Any
    lifecycle_case: Any
    observed: Any
    operation: Any
    overview_catalogues_before: Any
    payload: Any
    profile_id: Any
    projection_history_case: Any
    prorrata_before: Any
    prorrata_case: Any
    query_case: Any
    ratios_before: Any
    recipient_case: Any
    registry: Any
    resume_revision_catalogue_before: Any
    review_case: Any
    rule_case: Any
    submitted: Any
    tmp_path: Any
    withholding_seed: Any

    def resolve[ProjectionT: BaseModel](self, projection_type: type[ProjectionT]) -> ProjectionT:
        """Resolve one typed public result of the executed operation."""
        return _resolve_result_projection(
            self.driver,
            self.registry,
            definition_id=self.case.definition_id,
            operation_id=self.submitted.receipt.operation_id,
            terminal_revision=self.observed.projection.revision,
            projection_type=projection_type,
        )
