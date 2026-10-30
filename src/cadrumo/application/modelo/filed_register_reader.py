"""What the asset register yields now for the coordinates of a sealed revision.

The comparison runs through the same source owners a draft's verification reads, so a
filed :class:`CalculationRevision` and a draft cannot disagree about what the register says.
The pass reads the profile's :class:`TransactionCatalogue` through its ledger source owners.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import date, datetime
from typing import override

from ...core.errors.hierarchy import CadrumoError
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.calculation_revision_sources import ActivityAssetConsumption
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ...domain.renta.actividad_asset.claims import AmortizationClaim
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.transactions.date_partition import LedgerDatePartition
from ...domain.transactions.models import TransactionCatalogue
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..actividad_asset.history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from ..actividad_asset.ports import ActivityAssetHistoryRepository
from ..aggregation.ledger_filing_snapshot import FiledRegisterReader
from ..aggregation.ledger_membership import LedgerMembershipPorts, query_ledger_membership
from ..aggregation.modelo_bindings import (
    LedgerRentaGastosPagoFraccionadoAggregationSourceResolver,
    LedgerRentaIncomeAggregationSourceResolver,
)
from ..aggregation.modelo_bindings_renta_expenses import LedgerRentaGastosEstimacionDirectaAggregationSourceResolver
from ..invoices.catalogue_reads_ports import BucketBoundCatalogueReader, TransactionCatalogueReader
from .profile_readiness_gate import load_modelo_work_profile
from .work_profile import ModeloWorkProfile

_REGISTER_SOURCES = frozenset(
    {
        *LedgerRentaGastosEstimacionDirectaAggregationSourceResolver.owned_sources,
        *LedgerRentaGastosPagoFraccionadoAggregationSourceResolver.owned_sources,
        *LedgerRentaIncomeAggregationSourceResolver.owned_sources,
    },
)
"""The source families that read the asset register; no other Modelo can drift against it."""


class _PassHistory:
    """The asset register as one pass first read it, so each later revision reads that same history."""

    def __init__(self, inner: ActivityAssetHistoryRepository) -> None:
        self._inner = inner
        self._history: ActivityAssetHistory | None = None

    def load(self) -> ActivityAssetHistory:
        if self._history is None:
            self._history = self._inner.load()
        return self._history

    def append_revision(self, revision: ActivityAssetRevision) -> ActivityAssetHistory:
        self._history = None
        return self._inner.append_revision(revision)

    def apply(self, mutation: Callable[[ActivityAssetHistory], ActivityAssetHistory]) -> ActivityAssetHistory:
        self._history = None
        return self._inner.apply(mutation)

    def record_claim(
        self,
        claim: AmortizationClaim,
        *,
        expected_history: ActivityAssetHistory | None = None,
        recorded_at: datetime | None = None,
    ) -> ActivityAssetHistoryClaimResult:
        self._history = None
        return self._inner.record_claim(claim, expected_history=expected_history, recorded_at=recorded_at)


class _PassTransactionReads:
    """Transactions as one pass first read them, per question asked, so each later revision reuses the answer."""

    def __init__(self, inner: TransactionCatalogueReader) -> None:
        self._inner = inner
        self._catalogue: TransactionCatalogue | None = None
        self._partitions: dict[tuple[date, date], LedgerDatePartition] = {}

    @property
    def bucket_id(self) -> str | None:
        return self._inner.bucket_id if isinstance(self._inner, BucketBoundCatalogueReader) else None

    def load(self) -> TransactionCatalogue:
        if self._catalogue is None:
            self._catalogue = self._inner.load()
        return self._catalogue

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        key = (start, end)
        if key not in self._partitions:
            self._partitions[key] = self._inner.partition_by_date_range(start, end)
        return self._partitions[key]


class _PassTransactionRepository(_PassTransactionReads):
    """The repository form of the same pass-scoped reads."""

    def __init__(self, inner: TransactionCatalogueRepositoryProtocol) -> None:
        super().__init__(inner)
        self._repository = inner
        self._ranges: dict[tuple[date, date], TransactionCatalogue] = {}
        self._by_ids: dict[tuple[str, ...], TransactionCatalogue] = {}

    @property
    @override
    def bucket_id(self) -> str:
        return self._repository.bucket_id

    def exists(self) -> bool:
        return self._repository.exists()

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        key = (start, end)
        if key not in self._ranges:
            self._ranges[key] = self._repository.load_for_date_range(start, end)
        return self._ranges[key]

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        key = tuple(sorted(set(transaction_ids)))
        if key not in self._by_ids:
            self._by_ids[key] = self._repository.load_by_ids(key)
        return self._by_ids[key]

    def save(self, catalogue: TransactionCatalogue) -> None:
        raise PermissionError("a filed-register pass only reads transactions")


def _read_once_per_pass(ports: LedgerMembershipPorts) -> LedgerMembershipPorts:
    """Bind the asset history and the transactions to one load each for every revision of a pass."""
    return replace(
        ports,
        transaction_repository=_PassTransactionRepository(ports.transaction_repository),
        invoice_catalogue_read_ports=replace(
            ports.invoice_catalogue_read_ports,
            transaction_reader=_PassTransactionReads(ports.invoice_catalogue_read_ports.transaction_reader),
        ),
        activity_asset_history_repository=_PassHistory(ports.activity_asset_history_repository),
    )


def filed_register_reader(
    *,
    bucket_id: str,
    work_units: WorkUnitCatalogue,
    ports: LedgerMembershipPorts,
    operation: PinnedAuthorityOperation,
) -> FiledRegisterReader:
    """Bind the register comparison to one profile, its work units and one authority pin.

    A revision outside this bucket or reading no register source answers with what it
    recorded, so it shows no drift here.  A profile, registry revision or source that
    cannot be read answers ``None``.  The asset history and the transactions are read
    at most once for the reader's lifetime, so a reader serves one pass; a later pass
    binds a new one.

    Returns:
        A read-only reader of the register's current view of one revision.
    """
    profiles: list[ModeloWorkProfile | None] = []
    scoped: list[LedgerMembershipPorts] = []

    def read(target: CalculationRevision) -> ActivityAssetConsumption | None:
        recorded = target.activity_asset_consumption
        work_unit = work_units.get(target.work_unit_id)
        if work_unit is None or work_unit.bucket_id != bucket_id:
            return recorded
        try:
            revision = operation.revision(work_unit.modelo, work_unit.revision_id)
            if not {binding.source for binding in revision.bindings} & _REGISTER_SOURCES:
                return recorded
            if not scoped:
                scoped.append(_read_once_per_pass(ports))
            if not scoped[0].activity_asset_history_repository.load().revisions and recorded.is_empty:
                return recorded
            if not profiles:
                profiles.append(
                    load_modelo_work_profile(
                        bucket_id=bucket_id,
                        profile_decode_context=operation.profile_decode_context(),
                    ),
                )
        except (CadrumoError, LookupError):
            return None
        profile = profiles[0]
        if profile is None:
            return None
        membership = query_ledger_membership(
            target=target,
            work_unit=work_unit,
            revision=revision,
            profile=profile,
            ports=scoped[0],
            operation=operation,
        )
        return membership.activity_asset_consumption if membership.available else None

    return read


__all__ = ["filed_register_reader"]
