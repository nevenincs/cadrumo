"""Deterministic inward fakes for invoice creation policy tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from ....core.secure_object_write import SecureObjectWrite
from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.invoices.models import InvoiceCatalogue
from ..catalogue_creation_ports import CatalogueCreationPorts


class _InMemoryInvoiceRepository:
    """Minimal guarded catalogue mutation seam for application tests."""

    def __init__(self) -> None:
        self._catalogue = InvoiceCatalogue()

    def load(self) -> InvoiceCatalogue:
        return self._catalogue

    def mutate(self, mutation: Callable[[InvoiceCatalogue], InvoiceCatalogue]) -> InvoiceCatalogue:
        self._catalogue = mutation(self._catalogue)
        return self._catalogue


class _InMemoryEventRepository:
    """In-memory append-guard seam; no persistence behavior is asserted here."""

    def __init__(self) -> None:
        self._catalogue = BucketEventHistoryCatalogue()

    def exists(self) -> bool:
        return bool(self._catalogue.events)

    def load(self) -> BucketEventHistoryCatalogue:
        return self._catalogue

    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        self._catalogue = catalogue

    def load_revisioned(self) -> tuple[BucketEventHistoryCatalogue, str]:
        raise AssertionError("revisioned event loading is outside this creation fake")

    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        del catalogue, expected_revision_id
        raise AssertionError("secure event writes are outside this creation fake")

    def append_guarded(
        self,
        appender: Callable[[BucketEventHistoryCatalogue], BucketEventHistoryCatalogue],
        *,
        attempts: int = 4,
    ) -> BucketEventHistoryCatalogue:
        del attempts
        self._catalogue = appender(self._catalogue)
        return self._catalogue


class _InMemoryRateProvider:
    """No-rate provider for EUR-only invoice policy cases."""

    @property
    def rate_source_id(self) -> str:
        return "test_reference"

    def get_eur_rate(self, currency: str, rate_date: date) -> Decimal | None:
        del currency, rate_date
        return None


def in_memory_catalogue_creation_ports() -> CatalogueCreationPorts:
    """Compose fresh inward fakes for one application test scenario."""
    return CatalogueCreationPorts(
        invoice_repository=_InMemoryInvoiceRepository(),
        event_repository=_InMemoryEventRepository(),
        rate_provider=_InMemoryRateProvider(),
    )


__all__ = ["in_memory_catalogue_creation_ports"]
