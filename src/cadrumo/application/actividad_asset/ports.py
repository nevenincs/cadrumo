"""Application-owned capability for encrypted activity-asset history."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from ...domain.renta.actividad_asset.claims import AmortizationClaim
from ...domain.renta.actividad_asset.election import DirectEstimationRegime
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.transactions.models import TransactionCatalogue
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

    def record_claim(
        self,
        claim: AmortizationClaim,
        *,
        expected_history: ActivityAssetHistory | None = None,
    ) -> ActivityAssetHistoryClaimResult:
        """Record or replay a claim, optionally requiring its forecast history."""
        ...


class AcquisitionLedgerReader(Protocol):
    """Read the profile ledger rows an asset revision names as its acquisition."""

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        """Return the addressed rows; an absent identifier is omitted."""
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


__all__ = [
    "AcquisitionLedgerReader",
    "ActivityAssetHistoryRepository",
    "TaxpayerModalityReader",
    "TaxpayerWorkforceReader",
]
