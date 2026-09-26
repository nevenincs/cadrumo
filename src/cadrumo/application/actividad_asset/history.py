"""Append-only persisted history for IRPF activity assets."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.money.rounding import round_to_cents
from ...domain.renta.actividad_asset.claims import AmortizationClaim, asset_schedule_history, record_claim
from ...domain.renta.actividad_asset.errors import (
    ActividadAssetClaimConflictError,
    ActividadAssetIncompleteError,
    ActividadAssetValidationError,
)
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.renta.actividad_asset.schedule import require_method_continuity, require_opening_method


class ActivityAssetHistory(BaseModel):
    """One encrypted profile document containing immutable asset facts and claims."""

    model_config = STRICT_FROZEN_CONFIG

    revisions: tuple[ActivityAssetRevision, ...] = ()
    claims: tuple[AmortizationClaim, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_history(self) -> Self:
        revisions_by_id = {revision.revision_id: revision for revision in self.revisions}
        if len(revisions_by_id) != len(self.revisions):
            raise ValueError("activity asset history contains duplicate revision identities")
        asset_ids = {revision.asset_id for revision in self.revisions}
        for asset_id in asset_ids:
            self._validate_asset_revision_chain(asset_id)
        claim_ids = {claim.claim_id for claim in self.claims}
        if len(claim_ids) != len(self.claims):
            raise ValueError("activity asset history contains duplicate claim identities")
        for claim in self.claims:
            revision = revisions_by_id.get(claim.asset_revision_id)
            if revision is None:
                raise ValueError("activity asset claim references an unknown revision")
            if revision.asset_id != claim.asset_id:
                raise ValueError("activity asset claim identity does not match its revision")
            if revision.asset_kind is not claim.asset_kind:
                raise ValueError("activity asset claim kind does not match its revision")
        replayed_claims: tuple[AmortizationClaim, ...] = ()
        for claim in self.claims:
            replayed_claims = record_claim(replayed_claims, claim).claims
        return self

    def _validate_asset_revision_chain(self, asset_id: str) -> None:
        chain = tuple(revision for revision in self.revisions if revision.asset_id == asset_id)
        for position, revision in enumerate(chain, start=1):
            if revision.revision_number != position:
                raise ValueError("asset revisions must be append-only and consecutively numbered")
            expected_superseded_id = None if position == 1 else chain[position - 2].revision_id
            if revision.supersedes_revision_id != expected_superseded_id:
                raise ValueError("asset revision supersession must point to the prior revision of the same asset")

    def append_revision(self, revision: ActivityAssetRevision) -> ActivityAssetHistory:
        """Append an exact revision once, preserving each asset's correction chain."""
        if any(existing.revision_id == revision.revision_id for existing in self.revisions):
            return self
        return ActivityAssetHistory(revisions=(*self.revisions, revision), claims=self.claims)

    def record_claim(self, claim: AmortizationClaim) -> ActivityAssetHistoryClaimResult:
        """Record a claim through the domain replay/conflict contract.

        A new claim must also keep the asset's method continuity and stay
        within its remaining lawful basis.  The repository applies this inside
        its compare-and-swap mutation, so two forecasts taken against the same
        history can never both consume the same basis.
        """
        result = record_claim(self.claims, claim)
        if not result.reused_existing_claim:
            self._require_claim_invariants(claim, result.claims)
        return ActivityAssetHistoryClaimResult(
            history=ActivityAssetHistory(revisions=self.revisions, claims=result.claims),
            claim=result.claim,
            reused_existing_claim=result.reused_existing_claim,
        )

    def _require_claim_invariants(
        self,
        claim: AmortizationClaim,
        claims_after: tuple[AmortizationClaim, ...],
    ) -> None:
        revision = next((item for item in self.revisions if item.revision_id == claim.asset_revision_id), None)
        if revision is None:
            raise ActividadAssetValidationError("activity asset claim references an unknown revision")
        current = max(
            (item for item in self.revisions if item.asset_id == claim.asset_id),
            key=lambda item: item.revision_number,
        )
        if current.revision_id != revision.revision_id:
            raise ActividadAssetClaimConflictError("a new claim must be recorded under the asset's current revision")
        summary = asset_schedule_history(
            claims_after,
            self.revisions,
            asset_id=claim.asset_id,
            tax_year=claim.tax_year,
        )
        election = revision.amortization
        require_method_continuity(election.method, election.fingerprint, summary)
        require_opening_method(revision, election.method)
        opening = revision.opening_history.accumulated_amount
        if opening is None:
            raise ActividadAssetIncompleteError("opening amortization history is missing")
        consumed = opening + summary.accumulated_before_tax_year + summary.accumulated_in_tax_year
        if consumed > round_to_cents(revision.amortizable_basis()):
            raise ActividadAssetClaimConflictError("effective claims would exceed the asset's lawful amortizable basis")


class ActivityAssetHistoryClaimResult(BaseModel):
    """Claim replay result paired with the history document it leaves behind."""

    model_config = STRICT_FROZEN_CONFIG

    history: ActivityAssetHistory
    claim: AmortizationClaim
    reused_existing_claim: bool


__all__ = ["ActivityAssetHistory", "ActivityAssetHistoryClaimResult"]
