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

    def record_claim(
        self,
        claim: AmortizationClaim,
        *,
        expected_history: ActivityAssetHistory | None = None,
    ) -> ActivityAssetHistoryClaimResult:
        """Record a claim only while its optional forecast history remains current."""
        return self._repository.record_claim(claim, expected_history=expected_history)


__all__ = ["ActivityAssetHistoryService"]
