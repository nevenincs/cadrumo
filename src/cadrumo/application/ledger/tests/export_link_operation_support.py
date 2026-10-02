"""Synthetic atomic repositories for canonical export/link operation tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import cast, override

from ....core.classification.policies import SensitivityClass
from ....core.operations import profile_operation_subject
from ....core.secure_object_write import SecureObjectWrite
from ....core.time.clock import now
from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.invoices.models import Invoice, InvoiceCatalogue
from ....domain.iva.classification import InvoiceKind
from ....domain.transactions.models import TransactionCatalogue
from ...invoices.catalogue_creation import build_catalogue_invoice
from ...operations.owner import OperationExecutorContext
from ..persistence_ports import LedgerPersistenceConflictError
from .bulk_classify_operation_support import PROFILE_ID, CommitFence, EffectEvents, PrivateOperands
from .test_classification_rule_plan import (
    _ClassificationScenario,
    _EmptyInvoiceRepository,
    _InMemoryEventRepository,
    _InMemoryTransactionRepository,
    _transaction,
)


class Rates:
    """No network rates are needed to construct the synthetic EUR invoice."""

    rate_source_id = "synthetic"

    def get_eur_rate(self, currency: str, rate_date: date) -> Decimal | None:
        raise AssertionError("EUR fixture must not dispatch a rate lookup")


class Invoices(_EmptyInvoiceRepository):
    """Prepare a guarded invoice write without changing the stored catalogue."""

    @override
    def to_secure_object_write(
        self, catalogue: InvoiceCatalogue, *, expected_revision_id: str | None = None
    ) -> SecureObjectWrite:
        assert expected_revision_id == self._revision_id
        return SecureObjectWrite(
            namespace="test-link-invoices",
            object_key="invoices",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=now(),
            payload=catalogue.model_dump_json().encode("utf-8"),
        )


class Events(_InMemoryEventRepository):
    """Preparation records no audit event before the actual atomic writer."""

    @override
    def to_secure_object_write(
        self, catalogue: BucketEventHistoryCatalogue, *, expected_revision_id: str | None = None
    ) -> SecureObjectWrite:
        assert expected_revision_id == self._revision_id
        return SecureObjectWrite(
            namespace="test-link-events",
            object_key="events",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=now(),
            payload=catalogue.model_dump_json().encode("utf-8"),
        )


class Repository(_InMemoryTransactionRepository):
    """Reject legacy writes and simulate one guarded all-object commit boundary."""

    def __init__(self, catalogue: TransactionCatalogue, fence: CommitFence, invoices: Invoices, events: Events) -> None:
        super().__init__(catalogue)
        self.fence, self.invoices, self.events = fence, invoices, events
        self.revision = "a" * 64
        self.mode = "normal"
        self.commits = 0
        self.attempts = 0

    def load_revisioned(self) -> tuple[TransactionCatalogue, str]:
        assert not self.fence.active
        return self._catalogue, self.revision

    @override
    def save_with_secure_object_writes(
        self, catalogue: TransactionCatalogue, extra_writes: tuple[SecureObjectWrite, ...]
    ) -> None:
        raise AssertionError("export/link must never enter an unguarded writer")

    def save_if_revision_with_secure_object_writes(
        self, catalogue: TransactionCatalogue, *, expected_revision_id: str, extra_writes: tuple[SecureObjectWrite, ...]
    ) -> None:
        assert self.fence.active and extra_writes
        self.attempts += 1
        if self.mode == "conflict" or expected_revision_id != self.revision:
            raise LedgerPersistenceConflictError("synthetic guarded no-write conflict")
        invoices = self.invoices._catalogue
        events = self.events._catalogue
        for write in extra_writes:
            if write.namespace == "test-link-invoices":
                invoices = InvoiceCatalogue.model_validate_json(write.payload)
            elif write.namespace == "test-link-events":
                events = BucketEventHistoryCatalogue.model_validate_json(write.payload)
            else:
                raise AssertionError("unexpected canonical prepared object")
        self._catalogue, self.invoices._catalogue, self.events._catalogue = catalogue, invoices, events
        self.revision = "b" * 64
        self.commits += 1
        if self.mode == "uncertain":
            raise OSError("synthetic committed writer lost its acknowledgement")


class Subject:
    """Exact-profile authority and inward ports; no native storage acceptance claim."""

    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        self.operation = operation
        self.fence, self.effects, self.operands = CommitFence(), EffectEvents(), PrivateOperands()
        self.transaction = _transaction(provider_id="export-link", description="Synthetic export/link row")
        catalogue = TransactionCatalogue.from_transactions((self.transaction,))
        self.invoice: Invoice = build_catalogue_invoice(
            bucket_id=str(PROFILE_ID),
            kind=InvoiceKind.RECEIVED,
            counterparty_name="Synthetic supplier",
            counterparty_tax_id="B12345674",
            counterparty_country="ES",
            invoice_number="synthetic-link",
            issued_at=date(2024, 4, 10),
            currency="EUR",
            taxable_base=Decimal("10"),
            iva_rate=Decimal("21"),
            rate_provider=Rates(),
            operation=operation,
        )
        self.invoices, self.events = Invoices(), Events()
        self.invoices._catalogue = InvoiceCatalogue(invoices={self.invoice.invoice_id: self.invoice})
        self.repository = Repository(catalogue, self.fence, self.invoices, self.events)
        self.ports = replace(
            _ClassificationScenario(catalogue, operation=operation).ports,
            transaction_repository=self.repository,
            invoice_repository=self.invoices,
            bucket_event_repository=self.events,
        )

    def context(self, definition_id: str) -> OperationExecutorContext:
        return cast(
            OperationExecutorContext,
            cast(
                object,
                SimpleNamespace(
                    identity=SimpleNamespace(
                        definition_id=definition_id, subject_ref=profile_operation_subject(str(PROFILE_ID))
                    ),
                    authority_operation=self.operation,
                    cancellation=self.fence,
                    events=self.effects,
                    operands=self.operands,
                ),
            ),
        )
