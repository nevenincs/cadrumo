"""Application-owned capability for encrypted activity-asset history."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from ...domain.renta.actividad_asset.claims import AmortizationClaim
from ...domain.renta.actividad_asset.election import DirectEstimationRegime
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.renta.actividad_asset.schedule import AssetScheduleHistory, ScheduledAmortizationCharge
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

    def apply(self, mutation: Callable[[ActivityAssetHistory], ActivityAssetHistory]) -> ActivityAssetHistory:
        """Apply one pure change under compare-and-swap, retried against fresh state."""
        ...

    def record_claim(
        self,
        claim: AmortizationClaim,
        *,
        expected_history: ActivityAssetHistory | None = None,
        recorded_at: datetime | None = None,
    ) -> ActivityAssetHistoryClaimResult:
        """Record or replay a claim, optionally requiring its forecast history."""
        ...


class AcquisitionLedgerReader(Protocol):
    """Read the :class:`TransactionCatalogue` rows an asset revision names as its acquisition."""

    def load(self) -> TransactionCatalogue:
        """Return every row of the profile ledger."""
        ...

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        """Return the addressed rows; an absent identifier is omitted."""
        ...


class ActivityAssetForecastOperation(Protocol):
    """Trusted registry-backed forecast capability supplied by composition."""

    def __call__(
        self,
        revision: ActivityAssetRevision,
        *,
        covered_from: date,
        covered_until: date,
        history: AssetScheduleHistory,
        requested_free_amount: Decimal | None = None,
    ) -> ScheduledAmortizationCharge:
        """Resolve the revision's election and calculate one non-consuming forecast."""
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
    "ActivityAssetForecastOperation",
    "ActivityAssetHistoryRepository",
    "TaxpayerModalityReader",
    "TaxpayerWorkforceReader",
]
