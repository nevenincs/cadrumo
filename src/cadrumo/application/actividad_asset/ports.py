"""Application-owned capability for encrypted activity-asset history."""

from __future__ import annotations

from typing import Protocol

from ...domain.renta.actividad_asset.claims import AmortizationClaim
from ...domain.renta.actividad_asset.election import DirectEstimationRegime
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.user_profile.plantilla_media import PlantillaMediaYear
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


class TaxpayerModalityReader(Protocol):
    """Read the taxpayer profile's direct-estimation modality."""

    def __call__(self) -> DirectEstimationRegime:
        """Return the declared modality, refusing an absent or non-direct regime."""
        ...


class TaxpayerWorkforceReader(Protocol):
    """Read the taxpayer profile's declared average workforce per calendar year."""

    def __call__(self) -> tuple[PlantillaMediaYear, ...]:
        """Return the validated years in year order, empty when none is declared."""
        ...


__all__ = ["ActivityAssetHistoryRepository", "TaxpayerModalityReader", "TaxpayerWorkforceReader"]
