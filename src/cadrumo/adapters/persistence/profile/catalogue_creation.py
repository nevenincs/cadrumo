"""Outward adapters for the catalogue-invoice creation capability.

The application bundle exposes only domain catalogue values and application
errors.  These wrappers bind the existing encrypted repositories and ECB
provider to that contract, translating storage/upstream failures before they
reach an application caller.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
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
from ....application.invoices.catalogue_lifecycle_ports import CatalogueLifecyclePorts
from ....core.secure_object_write import SecureObjectWrite
from ....domain.buckets.errors import BucketEventValidationError
from ....domain.buckets.event import BucketEvent, BucketEventHistoryCatalogue
from ....domain.buckets.event_repository import BucketEventHistoryPersistenceError, append_bucket_event
from ....domain.currency.errors import ExchangeRateProviderError
from ....domain.currency.service import ExchangeRateProvider
from ....domain.invoices.errors import InvoicePersistenceError, InvoiceValidationError
from ....domain.invoices.models import InvoiceCatalogue
from ..storage.errors import SecureObjectRevisionConflictError, StorageError
from .buckets import BucketEventHistoryRepository
from .catalogue_reads import build_invoice_catalogue_read_ports
from .invoices import InvoiceCatalogueRepository


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
        """Commit the guarded invoice write with related secure objects."""
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
        :class:`~cadrumo.domain.invoices.models.InvoiceCatalogue`.
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
    ) -> None:
        """Bind the two secure singleton catalogues that share each batch."""
        self._invoice_repository = invoice_repository
        self._event_repository = event_repository

    @override
    def mutate_with_event(
        self,
        mutation: Callable[[InvoiceCatalogue], InvoiceCatalogue],
        event: BucketEvent,
        *,
        attempts: int = 4,
    ) -> InvoiceCatalogue:
        """Retry guarded composition without exposing a partial write."""
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
                self._invoice_repository.save_with_secure_object_writes(
                    updated,
                    expected_revision_id=invoice_revision_id,
                    extra_writes=(event_write,),
                )
            except SecureObjectRevisionConflictError as exc:
                last_conflict = exc
                continue
            except InvoiceValidationError:
                raise
            except (InvoicePersistenceError, BucketEventHistoryPersistenceError, StorageError, OSError) as exc:
                raise CatalogueInvoicePersistenceError("invoice_catalogue_and_event_commit") from exc
            return updated
        if last_conflict is not None:
            raise CatalogueInvoicePersistenceError("invoice_catalogue_and_event_commit_conflict") from last_conflict
        raise AssertionError("invoice audit co-commit exhausted without a conflict")


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
    def get_eur_rate(self, currency: str, rate_date: date) -> Decimal | None:
        """Fetch a rate while hiding outbound-provider failure types."""
        try:
            return self._provider.get_eur_rate(currency, rate_date)
        except (ExchangeRateProviderError, OSError) as exc:
            raise CatalogueInvoiceRateError("exchange_rate_lookup") from exc


def build_catalogue_creation_ports(*, bucket_id: str) -> CatalogueCreationPorts:
    """Bind the existing encrypted repositories and the host's rate provider for a bucket."""
    from ....application.exchange_rate_provider import exchange_rate_provider
    from ..storage.runtime_repository import secure_object_repository_for_bucket

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    invoice_repository = InvoiceCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects)
    event_repository = BucketEventHistoryRepository(objects=objects)
    return CatalogueCreationPorts(
        invoice_repository=CatalogueCreationInvoiceRepositoryAdapter(repository=invoice_repository),
        event_repository=CatalogueCreationEventRepositoryAdapter(repository=event_repository),
        audit_commit=CatalogueCreationAuditCommitAdapter(
            invoice_repository=invoice_repository,
            event_repository=event_repository,
        ),
        rate_provider=CatalogueCreationRateProviderAdapter(provider=exchange_rate_provider()),
    )


def build_catalogue_lifecycle_ports(*, bucket_id: str) -> CatalogueLifecyclePorts:
    """Bind read, mutation, and audit adapters for one invoice bucket."""
    normalized_bucket_id = bucket_id.strip()
    creation_ports = build_catalogue_creation_ports(bucket_id=normalized_bucket_id)
    return CatalogueLifecyclePorts(
        read_ports=build_invoice_catalogue_read_ports(bucket_id=normalized_bucket_id),
        invoice_repository=creation_ports.invoice_repository,
        event_repository=creation_ports.event_repository,
        audit_commit=creation_ports.audit_commit,
    )


__all__ = [
    "CatalogueCreationAuditCommitAdapter",
    "CatalogueCreationEventRepositoryAdapter",
    "CatalogueCreationInvoiceRepositoryAdapter",
    "CatalogueCreationRateProviderAdapter",
    "build_catalogue_creation_ports",
    "build_catalogue_lifecycle_ports",
]
