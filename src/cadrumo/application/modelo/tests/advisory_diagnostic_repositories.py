"""Typed empty repositories shared by calculate-path advisory tests.

The diagnostics coordinator requires complete repository protocols even in
tests whose modelo/period guards keep those repositories untouched. These
deterministic in-memory fakes reuse the behaviors already exercised by the
repository-specific application tests.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime

from ....core.observed_header_fact import ObservedHeaderFact
from ....core.period import Period
from ....core.secure_object_write import SecureObjectWrite
from ....domain.bienes_inversion.register import BienesInversionIvaRegister, BienInversionIvaRecord
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.ids import RevisionId
from ....domain.prorrata_register.register import (
    ProrrataActivityRow,
    ProrrataRegister,
    ProrrataRegisterEntry,
    SectorDefinition,
)
from ....domain.transactions.models import LedgerDatePartition, TransactionCatalogue
from ....domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ...bienes_inversion.ports import BienesInversionIvaRegisterRepositoryProtocol
from ...calculations.observations_repository import (
    CalculationObservationRepositoryProtocol,
    CalculationObservationStorageProtocol,
    ObservationEnvelopePayload,
    ObservationSourceKind,
    PriorDomiciliationElectionProjection,
    ResultDispositionProjection,
)
from ...prorrata_register.ports import ProrrataRegisterServiceRepositoryProtocol

__all__ = ["AdvisoryDiagnosticRepositories", "advisory_diagnostic_repositories"]


@dataclass(frozen=True, slots=True)
class AdvisoryDiagnosticRepositories:
    """Required repository ports for the coordinator's advisory pass."""

    observation: CalculationObservationRepositoryProtocol
    prorrata_register: ProrrataRegisterServiceRepositoryProtocol
    bienes_inversion: BienesInversionIvaRegisterRepositoryProtocol
    transactions: TransactionCatalogueRepositoryProtocol


def advisory_diagnostic_repositories(*, bucket_id: str) -> AdvisoryDiagnosticRepositories:
    """Return empty typed repositories for advisory cases without stored state."""
    return AdvisoryDiagnosticRepositories(
        observation=EmptyObservationRepository(),
        prorrata_register=InMemoryProrrataRegisterRepository(bucket_id=bucket_id),
        bienes_inversion=InMemoryBienesInversionRepository(BienesInversionIvaRegister()),
        transactions=EmptyTransactionCatalogueRepository(bucket_id=bucket_id),
    )


class EmptyObservationRepository:
    """Observation port with no prior filings; writes are outside these tests."""

    def load_observation(self, modelo: str, period: Period) -> ObservationEnvelopePayload | None:
        del modelo, period
        return None

    def iter_modelo(self, modelo: str) -> Iterator[ObservationEnvelopePayload]:
        del modelo
        return iter(())

    def iter_records(self) -> Iterator[ObservationEnvelopePayload]:
        return iter(())

    def prepare_observation_envelope(
        self,
        observation: RegistryModeloObservation,
        *,
        source_kind: ObservationSourceKind | str,
        stamped_revision_id: RevisionId,
        captured_at: datetime | None = None,
        member_nif: str | None = None,
        source_metadata: Mapping[str, str] | None = None,
        source_headers: tuple[ObservedHeaderFact, ...] = (),
        result_disposition: ResultDispositionProjection | None = None,
        prior_domiciliation_election: PriorDomiciliationElectionProjection | None = None,
        replace_official_evidence: bool = False,
    ) -> ObservationEnvelopePayload:
        del (
            observation,
            source_kind,
            stamped_revision_id,
            captured_at,
            member_nif,
            source_metadata,
            source_headers,
            result_disposition,
            prior_domiciliation_election,
            replace_official_evidence,
        )
        raise AssertionError("advisory diagnostics do not prepare observation envelopes")

    @staticmethod
    def save(payload: ObservationEnvelopePayload) -> None:
        del payload

    @staticmethod
    def to_secure_object_write(payload: ObservationEnvelopePayload) -> SecureObjectWrite:
        del payload
        raise AssertionError("advisory diagnostics do not write observation envelopes")

    @property
    def secure_object_repository(self) -> CalculationObservationStorageProtocol:
        return EmptyObservationStorage()


class EmptyObservationStorage:
    """Storage port that refuses writes if an advisory test reaches them."""

    @staticmethod
    def apply_batch(writes: tuple[SecureObjectWrite, ...]) -> None:
        del writes
        raise AssertionError("advisory diagnostics do not write secure objects")

    @property
    def engine(self) -> object:
        return self


class InMemoryProrrataRegisterRepository:
    """In-memory service repository copied from the prorrata policy test fake."""

    def __init__(self, *, bucket_id: str) -> None:
        self._bucket_id = bucket_id
        self._register = ProrrataRegister()

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def load(self) -> ProrrataRegister:
        return self._register

    def load_revisioned(self) -> tuple[ProrrataRegister, str]:
        return self._register, "test-revision"

    def to_secure_object_write(
        self,
        register: ProrrataRegister,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        del register, expected_revision_id
        raise AssertionError("advisory diagnostics do not write prorrata registers")

    def upsert_entry(self, entry: ProrrataRegisterEntry) -> ProrrataRegister:
        retained = tuple(
            existing
            for existing in self._register.entries
            if (existing.ejercicio, existing.sector_id) != (entry.ejercicio, entry.sector_id)
        )
        self._register = ProrrataRegister(
            entries=(*retained, entry),
            sector_definitions=self._register.sector_definitions,
            activity_rows=self._register.activity_rows,
        )
        return self._register

    def upsert_sector_definition(self, definition: SectorDefinition) -> ProrrataRegister:
        retained = tuple(
            existing for existing in self._register.sector_definitions if existing.sector_id != definition.sector_id
        )
        self._register = ProrrataRegister(
            entries=self._register.entries,
            sector_definitions=(*retained, definition),
            activity_rows=self._register.activity_rows,
        )
        return self._register

    def upsert_activity_row(self, row: ProrrataActivityRow) -> ProrrataRegister:
        retained = tuple(
            existing
            for existing in self._register.activity_rows
            if (existing.ejercicio, existing.activity_id) != (row.ejercicio, row.activity_id)
        )
        self._register = ProrrataRegister(
            entries=self._register.entries,
            sector_definitions=self._register.sector_definitions,
            activity_rows=(*retained, row),
        )
        return self._register


class InMemoryBienesInversionRepository:
    """In-memory register fake copied from the bienes advisory tests."""

    def __init__(self, register: BienesInversionIvaRegister) -> None:
        self._register = register

    def load(self) -> BienesInversionIvaRegister:
        return self._register

    def add(self, record: BienInversionIvaRecord) -> BienesInversionIvaRegister:
        self._register = BienesInversionIvaRegister(records=(*self._register.records, record))
        return self._register


class EmptyTransactionCatalogueRepository:
    """Empty transaction port copied from the Modelo 130 advisory tests."""

    def __init__(self, *, bucket_id: str) -> None:
        self._bucket_id = bucket_id

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    @staticmethod
    def exists() -> bool:
        return False

    @staticmethod
    def load() -> TransactionCatalogue:
        return TransactionCatalogue()

    @staticmethod
    def load_for_date_range(start: date, end: date) -> TransactionCatalogue:
        del start, end
        return TransactionCatalogue()

    @staticmethod
    def load_by_ids(transaction_ids: Iterable[str]) -> TransactionCatalogue:
        del transaction_ids
        return TransactionCatalogue()

    @staticmethod
    def partition_by_date_range(start: date, end: date) -> LedgerDatePartition:
        del start, end
        return LedgerDatePartition(in_window=TransactionCatalogue(), index_complete=True)

    @staticmethod
    def save(catalogue: TransactionCatalogue) -> None:
        del catalogue
