"""Thin application operations over one bucket-bound asset-history capability."""

from __future__ import annotations

from ...domain.renta.actividad_asset.claims import AmortizationClaim
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from .history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from .ports import ActivityAssetHistoryRepository


class ActivityAssetHistoryService:
    """Append and reopen history without deriving schedules or filing output."""

    def __init__(self, *, repository: ActivityAssetHistoryRepository) -> None:
        """Bind operations to the supplied bucket-scoped repository."""
        self._repository = repository

    def reopen(self) -> ActivityAssetHistory:
        """Return the complete immutable revision and claim history."""
        return self._repository.load()

    def append_revision(self, revision: ActivityAssetRevision) -> ActivityAssetHistory:
        """Append one reviewed asset revision."""
        return self._repository.append_revision(revision)

    def record_claim(self, claim: AmortizationClaim) -> ActivityAssetHistoryClaimResult:
        """Record or exactly replay one amortization claim."""
        return self._repository.record_claim(claim)


__all__ = ["ActivityAssetHistoryService"]
