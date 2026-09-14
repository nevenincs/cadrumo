"""Inward protocol fakes for review-source application tests.

These fakes keep application tests focused on source projection and queue
policy.  Concrete encrypted repositories are exercised by outer adapter
tests and are bound only from composition roots.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path

from ....application.filing.draft_review_ports import DraftReviewPorts
from ....domain.filing.schema import ModeloDraft
from ....domain.invoices.models import InvoiceCatalogue
from ....domain.transactions.models import TransactionCatalogue


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
        return self._catalogue or InvoiceCatalogue.from_invoices(())


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


class InMemoryObservationRepository:
    """Empty prior-filing observation capability for queue tests."""

    def iter_records(self) -> Iterator[object]:
        return iter(())


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
