"""Inward protocol fakes for review-source application tests.

These fakes keep application tests focused on source projection and queue
policy.  Concrete encrypted repositories are exercised by outer adapter
tests and are bound only from composition roots.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from datetime import date, datetime
from pathlib import Path

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ...calculations.observations_repository import (
    CalculationObservationStorageProtocol,
    ObservationEnvelopePayload,
    ObservationLayers,
    ObservationOverride,
    ObservationSourceKind,
    PriorDomiciliationElectionProjection,
    ResultDispositionProjection,
)
from ...filing.draft_review_ports import DraftReviewPorts
from ....core.period import Period
from ....core.secure_object_write import SecureObjectWrite
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.ids import RevisionId
from ....domain.filing.schema import ModeloDraft
from ....domain.invoices.models import InvoiceCatalogue
from ....domain.transactions.models import (
    LedgerDatePartition,
    OutOfWindowTransactionIndexEntry,
    OutOfWindowTransactionSummary,
    Transaction,
    TransactionCatalogue,
)


class InMemoryTransactionRepository:
    """Minimal transaction capability with an explicit optional failure."""

    def __init__(
        self,
        catalogue: TransactionCatalogue | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self._catalogue = catalogue
        self._error = error

    @property
    def bucket_id(self) -> str:
        return "test-bucket"

    def exists(self) -> bool:
        if self._error is not None:
            raise self._error
        return self._catalogue is not None

    def load(self) -> TransactionCatalogue:
        if self._error is not None:
            raise self._error
        return self._catalogue or TransactionCatalogue.from_transactions(())

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        catalogue = self.load()
        return TransactionCatalogue.from_transactions(
            transaction
            for transaction in catalogue
            if start <= (transaction.raw.value_date or transaction.raw.booked_date) <= end
        )

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        catalogue = self.load()
        requested = frozenset(transaction_ids)
        return TransactionCatalogue.from_transactions(
            transaction for transaction in catalogue if transaction.transaction_id in requested
        )

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        catalogue = self.load()
        in_window: list[Transaction] = []
        out_of_window: list[OutOfWindowTransactionIndexEntry] = []
        for transaction in catalogue:
            filing_date = transaction.raw.value_date or transaction.raw.booked_date
            if start <= filing_date <= end:
                in_window.append(transaction)
            else:
                out_of_window.append(
                    OutOfWindowTransactionIndexEntry(
                        transaction_id=transaction.transaction_id,
                        filing_date=filing_date,
                    )
                )
        return LedgerDatePartition(
            in_window=TransactionCatalogue.from_transactions(in_window),
            out_of_window=tuple(out_of_window),
            out_of_window_summary=OutOfWindowTransactionSummary.from_index_entries(out_of_window),
            index_complete=True,
        )

    def save(self, catalogue: TransactionCatalogue) -> None:
        if self._error is not None:
            raise self._error
        self._catalogue = catalogue

    def save_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        if extra_writes:
            raise AssertionError("review transaction fake does not support secure-object writes")
        self.save(catalogue)


class InMemoryInvoiceRepository:
    """Minimal invoice capability with an explicit optional failure."""

    def __init__(
        self,
        catalogue: InvoiceCatalogue | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self._catalogue = catalogue
        self._error = error

    @property
    def bucket_id(self) -> str:
        return "test-bucket"

    def exists(self) -> bool:
        if self._error is not None:
            raise self._error
        return self._catalogue is not None

    def load(self) -> InvoiceCatalogue:
        if self._error is not None:
            raise self._error
        return self._catalogue or build_invoice_catalogue(())

    def save(self, catalogue: InvoiceCatalogue) -> None:
        if self._error is not None:
            raise self._error
        self._catalogue = catalogue


class InMemoryDraftRepository:
    """Minimal draft capability returning secure logical path markers."""

    def __init__(
        self,
        drafts: tuple[ModeloDraft, ...] = (),
        *,
        error: Exception | None = None,
    ) -> None:
        self._drafts = drafts
        self._error = error

    def iter_drafts(self) -> Iterator[ModeloDraft]:
        if self._error is not None:
            raise self._error
        return iter(self._drafts)

    def envelope_path_for(self, identifier: str) -> Path:
        return Path("drafts") / f"{identifier}.json"


class _InMemoryObservationStorage:
    def apply_batch(self, writes: tuple[SecureObjectWrite, ...]) -> None:
        del writes
        raise AssertionError("review observation fake does not support secure-object writes")

    @property
    def engine(self) -> object:
        return self


class InMemoryObservationRepository:
    """Empty prior-filing observation capability for queue tests."""

    def __init__(self) -> None:
        self._storage = _InMemoryObservationStorage()
        self._records: list[ObservationEnvelopePayload] = []

    def load_observation(self, modelo: str, period: Period) -> ObservationEnvelopePayload | None:
        return next(
            (
                payload
                for payload in self._records
                if payload.observation.modelo == modelo and payload.observation.period == period.registry_token
            ),
            None,
        )

    def iter_modelo(self, modelo: str) -> Iterator[ObservationEnvelopePayload]:
        return (payload for payload in self._records if payload.observation.modelo == modelo)

    def iter_records(self) -> Iterator[ObservationEnvelopePayload]:
        return iter(self._records)

    def load_observation_layers(
        self,
        modelo: str,
        period: Period,
        *,
        member_nif: str | None = None,
    ) -> ObservationLayers:
        return ObservationLayers(
            modelo=modelo,
            filing_year=period.filing_year,
            period=period.registry_token,
            member_nif=member_nif,
        )

    def promote_pending_local(
        self,
        modelo: str,
        period: Period,
        *,
        member_nif: str | None = None,
        source_kind: ObservationSourceKind,
        source_metadata: Mapping[str, str],
        captured_at: datetime,
    ) -> tuple[SecureObjectWrite, ...]:
        del modelo, period, member_nif, source_kind, source_metadata, captured_at
        return ()

    def clear_pending_local(
        self,
        modelo: str,
        period: Period,
        *,
        member_nif: str | None = None,
        replacement_official: ObservationEnvelopePayload | None = None,
    ) -> tuple[SecureObjectWrite, ...]:
        del modelo, period, member_nif, replacement_official
        return ()

    def prepare_observation_envelope(
        self,
        observation: RegistryModeloObservation,
        *,
        source_kind: ObservationSourceKind | str,
        stamped_revision_id: RevisionId,
        captured_at: datetime | None = None,
        member_nif: str | None = None,
        source_metadata: Mapping[str, str] | None = None,
        source_headers: tuple[object, ...] = (),
        result_disposition: ResultDispositionProjection | None = None,
        prior_domiciliation_election: PriorDomiciliationElectionProjection | None = None,
        override: ObservationOverride | None = None,
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
            override,
        )
        raise AssertionError("review observation fake does not prepare envelopes")

    def save(self, payload: ObservationEnvelopePayload) -> None:
        self._records.append(payload)

    def to_secure_object_write(self, payload: ObservationEnvelopePayload) -> SecureObjectWrite:
        del payload
        raise AssertionError("review observation fake does not support secure-object writes")

    @property
    def secure_object_repository(self) -> CalculationObservationStorageProtocol:
        return self._storage


class InMemoryProfileRepository:
    """Stable profile projection used by approval-basis calculations."""

    def __init__(self, values: Mapping[str, str] | None = None) -> None:
        self._values = values if values is not None else {"identity.tax_id": "00000000T"}

    def load_path_values(self, *, bucket_id: str) -> Mapping[str, str] | None:
        del bucket_id
        return self._values


def draft_review_ports(
    *,
    transactions: TransactionCatalogue | None = None,
    invoices: InvoiceCatalogue | None = None,
    drafts: tuple[ModeloDraft, ...] = (),
    transaction_error: Exception | None = None,
    invoice_error: Exception | None = None,
    draft_error: Exception | None = None,
) -> DraftReviewPorts:
    """Build the complete required application port bundle for a test."""
    return DraftReviewPorts(
        transaction_repository=InMemoryTransactionRepository(
            transactions,
            error=transaction_error,
        ),
        invoice_repository=InMemoryInvoiceRepository(
            invoices,
            error=invoice_error,
        ),
        observation_repository=InMemoryObservationRepository(),
        profile_repository=InMemoryProfileRepository(),
        draft_repository=InMemoryDraftRepository(drafts, error=draft_error),
    )
