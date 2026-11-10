"""Cross-field requirements shared by the private and public activity-asset result contracts."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FourDigitYear
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period
from .activity_asset_contracts import ActivityAssetId
from .filing_handoff import ActivityAssetFilingHandoff
from .operation_dtos import ActivityAssetFilingHandoffSnapshot, ActivityAssetRevisionSnapshot


class ActivityAssetInspectionRevision(BaseModel):
    """One typed revision plus its deterministic identity for correction."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    revision: ActivityAssetRevisionSnapshot
    revision_id: Hex64Str

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _identity_matches(self) -> Self:
        if self.revision_id != self.revision.to_domain().revision_id:
            raise ValueError("activity-asset inspection revision identity does not reproduce")
        return self


def require_inspected_asset_revisions(
    *,
    outcome: Literal["succeeded", "refused"],
    asset_id: ActivityAssetId | None,
    revisions: tuple[ActivityAssetInspectionRevision, ...] | None,
) -> None:
    """Require a successful inspection to name its asset and describe only that asset."""
    if outcome == "succeeded" and asset_id is None:
        raise ValueError("successful activity-asset inspection must identify its asset")
    if revisions is not None and (
        not revisions or asset_id is None or any(item.revision.asset_id != asset_id for item in revisions)
    ):
        raise ValueError("activity-asset inspection revisions must describe the requested asset")


def require_claim_identity(claim_id: str | None, reproduced_claim_id: str | None) -> None:
    """Require a claim and its identity together, and the identity to reproduce from the claim."""
    if (reproduced_claim_id is None) != (claim_id is None):
        raise ValueError("activity-asset claim result and identity must appear together")
    if reproduced_claim_id is not None and claim_id != reproduced_claim_id:
        raise ValueError("activity-asset claim identity does not reproduce")


def require_filing_frame(
    *,
    outcome: Literal["succeeded", "refused"],
    tax_year: FourDigitYear | None,
    m130_period: str | None,
    filing_handoff: ActivityAssetFilingHandoff | ActivityAssetFilingHandoffSnapshot | None,
) -> None:
    """Require a handoff to sit inside the requested M100 tax year, and to state M130 exactly for a requested period."""
    if outcome == "succeeded" and tax_year is None:
        raise ValueError("successful activity-asset handoff must identify its filing frame")
    if filing_handoff is not None:
        if tax_year is None:
            raise ValueError("activity-asset filing handoff requires its requested filing frame")
        stated_years = {
            projection.tax_year
            for projection in (filing_handoff.material_m100, filing_handoff.intangible_m100)
            if projection is not None
        }
        if not stated_years <= {tax_year}:
            raise ValueError("activity-asset filing handoff differs from its requested tax year")
        if (m130_period is None) != (filing_handoff.material_m130 is None):
            raise ValueError("activity-asset filing handoff states Modelo 130 exactly for a requested period")
        if m130_period is not None:
            Period.from_year_and_code(tax_year, m130_period)


__all__ = [
    "ActivityAssetInspectionRevision",
    "require_claim_identity",
    "require_filing_frame",
    "require_inspected_asset_revisions",
]
