"""Encrypted atomic persistence for catalogue invoices and their audit history."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.outbound.fx.tests.recorded_ecb_rates import recorded_ecb_rate_provider
from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.catalogue_creation import (
    CatalogueCreationAuditCommitAdapter,
    CatalogueCreationEventRepositoryAdapter,
    CatalogueCreationInvoiceRepositoryAdapter,
    build_catalogue_creation_ports,
    build_catalogue_lifecycle_ports,
)
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.invoices.catalogue_creation import build_catalogue_invoice, create_catalogue_invoice
from cadrumo.application.invoices.catalogue_creation_ports import (
    CatalogueCreationPorts,
    CatalogueInvoicePersistenceError,
)
from cadrumo.application.invoices.catalogue_lifecycle import CatalogueInvoicePatch, update_catalogue_invoice
from cadrumo.domain.buckets.event import BucketEventObjectType, BucketEventType
from cadrumo.domain.buckets.event_repository import emit_bucket_event
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.iva.classification import InvoiceKind

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "76767676-7676-4767-8676-767676767676"
_OCCURRED_AT = datetime(2026, 9, 22, 11, 0, tzinfo=UTC)
_STALE_REVISION_ID = "0" * 64


@pytest.fixture(autouse=True)
def _authority_operation():
    with bundled_indexed_authority().operation():
        yield


def test_create_and_update_reopen_with_their_durable_audit_events(tmp_path: Path) -> None:
    """Both lifecycle writes survive a fresh encrypted repository opening with events."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        invoice = _invoice()
        created = create_catalogue_invoice(
            invoice=invoice,
            ports=build_catalogue_creation_ports(bucket_id=_BUCKET_ID),
            occurred_at=_OCCURRED_AT,
            actor="operator",
        )
        updated = update_catalogue_invoice(
            bucket_id=_BUCKET_ID,
            invoice_id=invoice.invoice_id,
            patch=CatalogueInvoicePatch(notes="Corrected local reference."),
            ports=build_catalogue_lifecycle_ports(bucket_id=_BUCKET_ID),
            occurred_at=_OCCURRED_AT,
            actor="operator",
        )

        reloaded_invoice = InvoiceCatalogueRepository(objects=profile.repository).load().get(invoice.invoice_id)
        events = BucketEventHistoryRepository(objects=profile.repository).load().events

    assert reloaded_invoice == updated.invoice
    assert created.bucket_event_ids[0] in events
    assert updated.bucket_event_ids[0] in events
    assert events[created.bucket_event_ids[0]].event_type is BucketEventType.PAYABLE_INVOICE_CREATED
    assert events[updated.bucket_event_ids[0]].event_type is BucketEventType.PAYABLE_INVOICE_UPDATED


def test_mid_batch_event_conflict_leaves_neither_invoice_nor_event(tmp_path: Path) -> None:
    """A stale second write rolls back the invoice write that preceded it in the batch."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        invoice = _invoice()
        invoice_repository = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        event_repository = BucketEventHistoryRepository(objects=profile.repository)
        event_repository.save(event_repository.load())
        ports = _ports_with_stale_event_revision(
            invoice_repository=invoice_repository,
            event_repository=event_repository,
        )

        with pytest.raises(CatalogueInvoicePersistenceError, match="commit_conflict"):
            create_catalogue_invoice(
                invoice=invoice,
                ports=ports,
                occurred_at=_OCCURRED_AT,
                actor="operator",
            )

        reloaded_invoices = InvoiceCatalogueRepository(objects=profile.repository).load()
        reloaded_events = BucketEventHistoryRepository(objects=profile.repository).load().events

    assert invoice.invoice_id not in reloaded_invoices
    assert not any(event.object_id == invoice.invoice_id for event in reloaded_events.values())


def test_event_revision_race_retries_without_losing_either_event(tmp_path: Path) -> None:
    """A competing audit append forces a retry and remains durable with the invoice event."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        invoice = _invoice()
        events = BucketEventHistoryRepository(objects=profile.repository)
        invoice_repository = _EventInterleavingInvoiceRepository(
            InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository),
            events,
        )
        base_ports = build_catalogue_creation_ports(bucket_id=_BUCKET_ID)
        ports = CatalogueCreationPorts(
            invoice_repository=base_ports.invoice_repository,
            event_repository=base_ports.event_repository,
            audit_commit=CatalogueCreationAuditCommitAdapter(
                invoice_repository=invoice_repository,
                event_repository=events,
            ),
            rate_provider=base_ports.rate_provider,
        )

        result = create_catalogue_invoice(
            invoice=invoice,
            ports=ports,
            occurred_at=_OCCURRED_AT,
            actor="operator",
        )
        reloaded_invoices = InvoiceCatalogueRepository(objects=profile.repository).load()
        reloaded_events = BucketEventHistoryRepository(objects=profile.repository).load().events

    assert reloaded_invoices.get(invoice.invoice_id) == invoice
    assert result.bucket_event_ids[0] in reloaded_events
    assert any(event.object_id == "concurrent-audit-entry" for event in reloaded_events.values())


def _ports_with_stale_event_revision(
    *,
    invoice_repository: InvoiceCatalogueRepository,
    event_repository: BucketEventHistoryRepository,
) -> CatalogueCreationPorts:
    return CatalogueCreationPorts(
        invoice_repository=CatalogueCreationInvoiceRepositoryAdapter(repository=invoice_repository),
        event_repository=CatalogueCreationEventRepositoryAdapter(repository=event_repository),
        audit_commit=CatalogueCreationAuditCommitAdapter(
            invoice_repository=invoice_repository,
            event_repository=_StaleEventRevisionRepository(event_repository),
        ),
        rate_provider=recorded_ecb_rate_provider(),
    )


class _StaleEventRevisionRepository:
    """Offer a stale event revision so the second write fails inside the batch."""

    def __init__(self, delegate: BucketEventHistoryRepository) -> None:
        self._delegate = delegate

    def load_revisioned(self):
        catalogue, _revision_id = self._delegate.load_revisioned()
        return catalogue, _STALE_REVISION_ID

    def to_secure_object_write(self, *args, **kwargs):
        return self._delegate.to_secure_object_write(*args, **kwargs)


class _EventInterleavingInvoiceRepository:
    """Append an unrelated event after the first event revision has been read."""

    def __init__(self, delegate: InvoiceCatalogueRepository, events: BucketEventHistoryRepository) -> None:
        self._delegate = delegate
        self._events = events
        self._interleaved = False

    def load_revisioned(self):
        return self._delegate.load_revisioned()

    def save_with_secure_object_writes(self, *args, **kwargs) -> None:
        if not self._interleaved:
            self._interleaved = True
            emit_bucket_event(
                repository=self._events,
                bucket_id=_BUCKET_ID,
                event_type=BucketEventType.PROFILE_VALUES_UPDATED,
                occurred_at=_OCCURRED_AT,
                actor="concurrent-operator",
                object_type=BucketEventObjectType.PROFILE,
                object_id="concurrent-audit-entry",
                payload={"marker": "concurrent-audit-entry"},
                payload_version=1,
            )
        self._delegate.save_with_secure_object_writes(*args, **kwargs)


def _invoice():
    return build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Papeleria Sol SL",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="ATOMIC-2026-001",
        issued_at=date(2026, 9, 22),
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
        rate_provider=recorded_ecb_rate_provider(),
    )
