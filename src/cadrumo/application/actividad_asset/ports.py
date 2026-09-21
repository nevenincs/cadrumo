"""Application-owned capability for encrypted activity-asset history."""

from __future__ import annotations

from typing import Protocol

from ...domain.renta.actividad_asset.claims import AmortizationClaim
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from .history import ActivityAssetHistory, ActivityAssetHistoryClaimResult


class ActivityAssetHistoryRepository(Protocol):
    """Required bucket-bound repository for append-only asset histories."""

    def load(self) -> ActivityAssetHistory:
        """Return the complete history, or the empty document when absent."""
        ...

    def append_revision(self, revision: ActivityAssetRevision) -> ActivityAssetHistory:
        """Append an immutable asset revision and return the reopened history."""
        ...

    def record_claim(self, claim: AmortizationClaim) -> ActivityAssetHistoryClaimResult:
        """Record or replay a claim according to its deterministic identity."""
        ...


__all__ = ["ActivityAssetHistoryRepository"]
