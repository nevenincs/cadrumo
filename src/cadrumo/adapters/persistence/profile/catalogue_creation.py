"""Outward adapters for the catalogue-invoice creation capability.

The application bundle exposes only domain catalogue values and application
errors.  These wrappers bind the existing encrypted repositories and ECB
provider to that contract, translating storage/upstream failures before they
reach an application caller;
:class:`CalculationRevision`, the saved calculation revision.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Protocol, override

from ....application.invoices.catalogue_creation_ports import (
    CatalogueCreationPorts,
    CatalogueInvoiceAuditCommitPort,
    CatalogueInvoiceEventRepositoryPort,
    CatalogueInvoicePersistenceError,
    CatalogueInvoiceRateError,
    CatalogueInvoiceRateProviderPort,
    CatalogueInvoiceRepositoryPort,
)
from ....application.invoices.catalogue_intake_operation_ports import InvoiceIntakeCommitConflictError
from ....application.invoices.catalogue_lifecycle_ports import CatalogueLifecyclePorts
from ....core.secure_object_write import SecureObjectWrite
from ....domain.buckets.errors import BucketEventValidationError
from ....domain.buckets.event import BucketEvent, BucketEventHistoryCatalogue
from ....domain.buckets.event_repository import BucketEventHistoryPersistenceError, append_bucket_event
from ....domain.calculations.registry.tax_id_format import SubjectTaxId
from ....domain.currency.errors import ExchangeRateProviderError
from ....domain.currency.models import EurRateLookup
from ....domain.currency.service import ExchangeRateProvider
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.invoices.errors import InvoicePersistenceError, InvoiceValidationError
from ....domain.modelos.calculation_revision import SEALED_REVISION_STATES, CalculationRevision
from ....domain.modelos.work_unit import WorkUnit
from ..storage.attachment import AttachmentStore
from ..storage.errors import SecureObjectRevisionConflictError, StorageError
from .buckets import BucketEventHistoryRepository
from .catalogue_reads import build_invoice_catalogue_read_ports
from .invoices import InvoiceCatalogueRepository
from .modelos_calculation import CalculationRevisionCatalogueRepository
from .modelos_work_units import WorkUnitCatalogueRepository


class _InvoiceAuditRepository(Protocol):
    """Concrete co-commit operations the audit adapter needs from invoices."""

    def load_revisioned(self) -> tuple[InvoiceCatalogue, str]:
        """Return the invoice singleton and its observed revision."""
        ...

    def save_with_secure_object_writes(
        self,
        catalogue: InvoiceCatalogue,
        *,
        expected_revision_id: str,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Commit the guarded invoice write with related secure objects.

        Core types:
        :class:`~cadrumo.domain.invoices.catalogue.InvoiceCatalogue`.
        """
        ...


class _EventAuditRepository(Protocol):
    """Concrete event-history operations the audit adapter needs."""

    def load_revisioned(self) -> tuple[BucketEventHistoryCatalogue, str]:
        """Return the audit singleton and its observed revision."""
        ...

    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Prepare a guarded event-history write without committing it."""
        ...


class CatalogueCreationInvoiceRepositoryAdapter(CatalogueInvoiceRepositoryPort):
    """Translate the encrypted invoice repository to the creation port."""

    def __init__(self, *, repository: InvoiceCatalogueRepository) -> None:
        """Bind the encrypted invoice catalogue repository."""
        self._repository = repository

    @override
    def load(self) -> InvoiceCatalogue:
        """Load one catalogue, hiding storage-specific failure types."""
        try:
            return self._repository.load()
        except (InvoicePersistenceError, StorageError, OSError) as exc:
            raise CatalogueInvoicePersistenceError("invoice_catalogue_load") from exc

    @override
    def mutate(self, mutation: Callable[[InvoiceCatalogue], InvoiceCatalogue]) -> InvoiceCatalogue:
        """Apply one guarded mutation, preserving domain validation refusals.

        Core types:
        :class:`~cadrumo.domain.invoices.catalogue.InvoiceCatalogue`.
        """
        try:
            return self._repository.mutate(mutation)
        except InvoiceValidationError:
            raise
        except (InvoicePersistenceError, StorageError, OSError) as exc:
            raise CatalogueInvoicePersistenceError("invoice_catalogue_mutate") from exc


class CatalogueCreationEventRepositoryAdapter(CatalogueInvoiceEventRepositoryPort):
    """Translate the encrypted bucket-event repository to the creation port."""

    def __init__(self, *, repository: BucketEventHistoryRepository) -> None:
        """Bind the encrypted bucket-event history repository."""
        self._repository = repository

    @override
    def exists(self) -> bool:
        """Report event-history presence through the application contract."""
        try:
            return self._repository.exists()
        except (BucketEventHistoryPersistenceError, StorageError, OSError) as exc:
            raise CatalogueInvoicePersistenceError("bucket_event_history_exists") from exc

    @override
    def load(self) -> BucketEventHistoryCatalogue:
        """Load event history, hiding storage-specific failure types."""
        try:
            return self._repository.load()
        except (BucketEventHistoryPersistenceError, StorageError, OSError) as exc:
            raise CatalogueInvoicePersistenceError("bucket_event_history_load") from exc

    def load_revisioned(self) -> tuple[BucketEventHistoryCatalogue, str]:
        """Load event history and its compare-and-swap revision."""
        try:
            return self._repository.load_revisioned()
        except (BucketEventHistoryPersistenceError, StorageError, OSError) as exc:
            raise CatalogueInvoicePersistenceError("bucket_event_history_load") from exc

    @override
    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        """Persist event history through the existing encrypted repository."""
        try:
            self._repository.save(catalogue)
        except (BucketEventHistoryPersistenceError, StorageError, OSError) as exc:
            raise CatalogueInvoicePersistenceError("bucket_event_history_save") from exc

    @override
    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Prepare the inherited co-commit write capability."""
        try:
            return self._repository.to_secure_object_write(
                catalogue,
                expected_revision_id=expected_revision_id,
            )
        except (BucketEventHistoryPersistenceError, StorageError, OSError) as exc:
            raise CatalogueInvoicePersistenceError("bucket_event_history_prepare_write") from exc

    @override
    def append_guarded(
        self,
        appender: Callable[[BucketEventHistoryCatalogue], BucketEventHistoryCatalogue],
        *,
        attempts: int = 4,
    ) -> BucketEventHistoryCatalogue:
        """Append one event through the repository revision guard."""
        try:
            return self._repository.append_guarded(appender, attempts=attempts)
        except BucketEventValidationError:
            raise
        except BucketEventHistoryPersistenceError as exc:
            raise CatalogueInvoicePersistenceError("bucket_event_history_append") from exc
        except (StorageError, OSError) as exc:
            raise CatalogueInvoicePersistenceError("bucket_event_history_append") from exc


class CatalogueCreationAuditCommitAdapter(CatalogueInvoiceAuditCommitPort):
    """Co-commit one invoice mutation and one bucket event under both guards."""

    def __init__(
        self,
        *,
        invoice_repository: _InvoiceAuditRepository,
        event_repository: _EventAuditRepository,
        commit: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        """Bind the two secure singleton catalogues that share each batch."""
        self._invoice_repository = invoice_repository
        self._event_repository = event_repository
        self._commit = commit

    @override
    def mutate_with_event(
        self,
        mutation: Callable[[InvoiceCatalogue], InvoiceCatalogue],
        event: BucketEvent,
        *,
        attempts: int = 4,
    ) -> InvoiceCatalogue:
        """Retry guarded composition without exposing a partial write.

        Core types:
        :class:`~cadrumo.domain.invoices.catalogue.InvoiceCatalogue`.
        """
        last_conflict: SecureObjectRevisionConflictError | None = None
        for _attempt in range(attempts):
            try:
                current, invoice_revision_id = self._invoice_repository.load_revisioned()
                updated = mutation(current)
                events, event_revision_id = self._event_repository.load_revisioned()
                event_write = self._event_repository.to_secure_object_write(
                    append_bucket_event(events, event),
                    expected_revision_id=event_revision_id,
                )

                self._commit_prepared_invoice_batch(updated, invoice_revision_id, event_write)
            except SecureObjectRevisionConflictError as exc:
                last_conflict = exc
                continue
            except InvoiceIntakeCommitConflictError as exc:
                if not isinstance(exc.__cause__, SecureObjectRevisionConflictError):
                    raise
                last_conflict = exc.__cause__
                continue
            except InvoiceValidationError:
                raise
            except (InvoicePersistenceError, BucketEventHistoryPersistenceError, StorageError, OSError) as exc:
                raise CatalogueInvoicePersistenceError("invoice_catalogue_and_event_commit") from exc
            return updated
        if last_conflict is not None:
            raise CatalogueInvoicePersistenceError("invoice_catalogue_and_event_commit_conflict") from last_conflict
        raise AssertionError("invoice audit co-commit exhausted without a conflict")

    def _commit_prepared_invoice_batch(
        self, updated: InvoiceCatalogue, invoice_revision_id: str, event_write: SecureObjectWrite
    ) -> None:
        """Submit one prepared co-write through the optional intake commit fence."""

        def save(
            prepared: InvoiceCatalogue = updated,
            prepared_revision_id: str = invoice_revision_id,
            prepared_event: SecureObjectWrite = event_write,
        ) -> None:
            try:
                self._invoice_repository.save_with_secure_object_writes(
                    prepared,
                    expected_revision_id=prepared_revision_id,
                    extra_writes=(prepared_event,),
                )
            except SecureObjectRevisionConflictError as exc:
                if self._commit is None:
                    raise
                raise InvoiceIntakeCommitConflictError("prepared invoice batch lost its CAS revision") from exc

        if self._commit is None:
            save()
        else:
            self._commit(save)


class CatalogueCreationRateProviderAdapter(CatalogueInvoiceRateProviderPort):
    """Translate the host's exchange-rate provider to the application rate capability."""

    def __init__(self, *, provider: ExchangeRateProvider) -> None:
        """Bind the host-composed exchange-rate provider."""
        self._provider = provider

    @property
    @override
    def rate_source_id(self) -> str:
        """Return the provider's stable authority identifier."""
        return self._provider.rate_source_id

    @override
    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        """Look up a rate while hiding outbound-provider failure types."""
        try:
            return self._provider.lookup_eur_rate(currency, rate_date)
        except (ExchangeRateProviderError, OSError) as exc:
            raise CatalogueInvoiceRateError("exchange_rate_lookup") from exc


@dataclass(frozen=True, slots=True)
class CatalogueSealedRevisionReaderAdapter:
    """Read the sealed revisions of one bucket from its modelo repositories."""

    bucket_id: str
    work_unit_repository: WorkUnitCatalogueRepository
    calculation_repository: CalculationRevisionCatalogueRepository

    def sealed_revisions(self) -> tuple[tuple[CalculationRevision, WorkUnit], ...]:
        """Scan the live catalogues, never a derived index, as the ledger guard does."""
        work_units = self.work_unit_repository.load()
        sealed: list[tuple[CalculationRevision, WorkUnit]] = []
        for revision in self.calculation_repository.load().values():
            if revision.state not in SEALED_REVISION_STATES:
                continue
            work_unit = work_units.get(revision.work_unit_id)
            if work_unit is not None and work_unit.bucket_id == self.bucket_id:
                sealed.append((revision, work_unit))
        return tuple(sealed)


def _catalogue_repositories(
    *, bucket_id: str
) -> tuple[InvoiceCatalogueRepository, BucketEventHistoryRepository, AttachmentStore]:
    """Bind local invoice, audit and document storage without resolving an outbound provider."""
    from ..storage.runtime_repository import secure_object_repository_for_bucket

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    invoice_repository = InvoiceCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects)
    event_repository = BucketEventHistoryRepository(objects=objects)
    return invoice_repository, event_repository, AttachmentStore(objects=objects, bucket_id=normalized_bucket_id)


def build_catalogue_creation_ports(
    *,
    bucket_id: str,
    commit: Callable[[Callable[[], None]], None] | None = None,
) -> CatalogueCreationPorts:
    """Bind the existing encrypted repositories and the host's rate provider for a bucket."""
    from ....application.exchange_rate_provider import exchange_rate_provider

    invoice_repository, event_repository, documents = _catalogue_repositories(bucket_id=bucket_id)
    return CatalogueCreationPorts(
        invoice_repository=CatalogueCreationInvoiceRepositoryAdapter(repository=invoice_repository),
        event_repository=CatalogueCreationEventRepositoryAdapter(repository=event_repository),
        audit_commit=CatalogueCreationAuditCommitAdapter(
            invoice_repository=invoice_repository,
            event_repository=event_repository,
            commit=commit,
        ),
        rate_provider=CatalogueCreationRateProviderAdapter(provider=exchange_rate_provider()),
        documents=documents,
    )


def build_catalogue_lifecycle_ports(
    *,
    bucket_id: str,
    taxpayer_tax_id: SubjectTaxId | None = None,
    mutation_writer: Callable[[Callable[[], None]], None] | None = None,
) -> CatalogueLifecyclePorts:
    """Bind read, mutation, and audit adapters for one invoice bucket.

    ``taxpayer_tax_id`` is the profile's own tax identity. The sealed-revision
    scan decodes every stored calculation revision, and an M303 rectificativa
    cannot be decoded without it, so a bucket holding one refuses every invoice
    correction when the scan runs without.

    ``mutation_writer`` admits every commit the bundle makes: the invoice, its
    audit event and any other secure object all share one fenced repository.
    """
    normalized_bucket_id = bucket_id.strip()
    from ..storage.runtime_repository import secure_object_repository_for_bucket

    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    if mutation_writer is not None:
        objects = objects.with_mutation_writer(mutation_writer)
    invoice_repository = InvoiceCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects)
    event_repository = BucketEventHistoryRepository(objects=objects)
    return CatalogueLifecyclePorts(
        read_ports=build_invoice_catalogue_read_ports(bucket_id=normalized_bucket_id),
        invoice_repository=CatalogueCreationInvoiceRepositoryAdapter(repository=invoice_repository),
        event_repository=CatalogueCreationEventRepositoryAdapter(repository=event_repository),
        audit_commit=CatalogueCreationAuditCommitAdapter(
            invoice_repository=invoice_repository,
            event_repository=event_repository,
        ),
        sealed_revisions=CatalogueSealedRevisionReaderAdapter(
            bucket_id=normalized_bucket_id,
            work_unit_repository=WorkUnitCatalogueRepository(objects=objects),
            calculation_repository=CalculationRevisionCatalogueRepository(
                objects=objects,
                m303_rectificativa_taxpayer_tax_id=taxpayer_tax_id,
            ),
        ),
        documents=AttachmentStore(objects=objects, bucket_id=normalized_bucket_id),
    )


__all__ = [
    "CatalogueCreationAuditCommitAdapter",
    "CatalogueCreationEventRepositoryAdapter",
    "CatalogueCreationInvoiceRepositoryAdapter",
    "CatalogueCreationRateProviderAdapter",
    "CatalogueSealedRevisionReaderAdapter",
    "build_catalogue_creation_ports",
    "build_catalogue_lifecycle_ports",
]
