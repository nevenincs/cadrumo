"""Thin application operations over one bucket-bound asset-history capability."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from ...domain.renta.actividad_asset.claims import AmortizationClaim
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

    def apply(self, mutation: Callable[[ActivityAssetHistory], ActivityAssetHistory]) -> ActivityAssetHistory:
        """Apply one pure change to the history in a single compare-and-swap."""
        return self._repository.apply(mutation)

    def record_claim(
        self,
        claim: AmortizationClaim,
        *,
        expected_history: ActivityAssetHistory | None = None,
        recorded_at: datetime | None = None,
    ) -> ActivityAssetHistoryClaimResult:
        """Record a claim only while its optional forecast history remains current."""
        return self._repository.record_claim(claim, expected_history=expected_history, recorded_at=recorded_at)


__all__ = ["ActivityAssetHistoryService"]
