"""Actual encrypted co-commit callback placement and canonical CAS retries."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.invoices.catalogue_creation import build_catalogue_invoice, create_catalogue_invoice
from .....application.invoices.catalogue_intake_operation_ports import InvoiceIntakeCommitConflictError
from .....core.hashing import canonical_json_bytes, sha256_hex
from .....core.secure_object_write import SecureObjectWrite
from .....domain.buckets.event import BucketEventHistoryCatalogue, BucketEventType
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from .....domain.invoices.models import InvoiceCatalogue
from .....domain.iva.classification import InvoiceKind
from ....outbound.fx.tests.recorded_ecb_rates import recorded_ecb_rate_provider
from ...storage.errors import SecureObjectRevisionConflictError
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..buckets import BucketEventHistoryRepository
from ..catalogue_creation import CatalogueCreationAuditCommitAdapter, build_catalogue_creation_ports
from ..invoices import InvoiceCatalogueRepository

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]
_PROFILE = "76767676-7676-4767-8676-767676767676"


@pytest.mark.parametrize("conflict_once", [False, True], ids=["prepared-one-batch", "atomic-conflict-retry"])
def test_admission_starts_after_both_cas_reads_and_event_preparation_and_ends_after_save(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, conflict_once: bool
) -> None:
    trace: list[str] = []
    inside = False
    conflicts = 0
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE) as profile,
        validating_governed_facts(authority_operation),
    ):
        invoices = InvoiceCatalogueRepository(bucket_id=_PROFILE, objects=profile.repository)
        events = BucketEventHistoryRepository(objects=profile.repository)
        baseline_invoices = invoices.load()
        baseline_events = events.load()
        baseline_event_ids = frozenset(baseline_events.events)
        baseline_event_digest = sha256_hex(canonical_json_bytes(baseline_events.model_dump(mode="json")))

        def assert_baseline_preserved(current: BucketEventHistoryCatalogue) -> None:
            assert baseline_event_ids <= current.events.keys()
            retained = BucketEventHistoryCatalogue(events={key: current.events[key] for key in baseline_event_ids})
            assert sha256_hex(canonical_json_bytes(retained.model_dump(mode="json"))) == baseline_event_digest

        class InvoiceRepository:
            def load_revisioned(self) -> tuple[InvoiceCatalogue, str]:
                assert not inside
                trace.append("invoice_cas")
                return invoices.load_revisioned()

            def save_with_secure_object_writes(
                self,
                catalogue: InvoiceCatalogue,
                *,
                expected_revision_id: str,
                extra_writes: tuple[SecureObjectWrite, ...],
            ) -> None:
                nonlocal conflicts
                assert inside and trace[-1] == "admitted" and len(extra_writes) == 1
                trace.append("actual_save")
                if conflict_once and conflicts == 0:
                    conflicts += 1
                    raise SecureObjectRevisionConflictError("synthetic CAS race before atomic dispatch")
                invoices.save_with_secure_object_writes(
                    catalogue, expected_revision_id=expected_revision_id, extra_writes=extra_writes
                )

        class EventRepository:
            def load_revisioned(self) -> tuple[BucketEventHistoryCatalogue, str]:
                assert not inside
                trace.append("event_cas")
                return events.load_revisioned()

            def to_secure_object_write(
                self, catalogue: BucketEventHistoryCatalogue, *, expected_revision_id: str | None = None
            ) -> SecureObjectWrite:
                assert not inside
                trace.append("event_prepared")
                return events.to_secure_object_write(catalogue, expected_revision_id=expected_revision_id)

        def commit(save: Callable[[], None]) -> None:
            nonlocal inside
            assert trace[-3:] == ["invoice_cas", "event_cas", "event_prepared"]
            inside = True
            trace.append("admitted")
            try:
                save()
                current_events = events.load()
                assert_baseline_preserved(current_events)
                new_event_ids = current_events.events.keys() - baseline_event_ids
                assert len(new_event_ids) == 1 and invoices.load() != baseline_invoices
                assert all(
                    current_events.events[key].event_type is BucketEventType.PAYABLE_INVOICE_CREATED
                    for key in new_event_ids
                )
                trace.append("acknowledged")
            except InvoiceIntakeCommitConflictError:
                current_events = events.load()
                assert invoices.load() == baseline_invoices and frozenset(current_events.events) == baseline_event_ids
                assert_baseline_preserved(current_events)
                trace.append("definitive_no_write")
                raise
            finally:
                inside = False

        ports = build_catalogue_creation_ports(bucket_id=_PROFILE)
        ports = replace(
            ports,
            audit_commit=CatalogueCreationAuditCommitAdapter(
                invoice_repository=InvoiceRepository(), event_repository=EventRepository(), commit=commit
            ),
            rate_provider=recorded_ecb_rate_provider(),
        )
        invoice = build_catalogue_invoice(
            bucket_id=_PROFILE,
            kind=InvoiceKind.RECEIVED,
            counterparty_name="Synthetic supplier",
            counterparty_tax_id="A58818501",
            counterparty_country="ES",
            invoice_number="PREPARED-1",
            issued_at=date(2026, 5, 1),
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("21"),
            currency="EUR",
            rate_provider=ports.rate_provider,
            operation=authority_operation,
        )
        created = create_catalogue_invoice(invoice=invoice, ports=ports)
        assert InvoiceCatalogueRepository(objects=profile.repository).load().get(invoice.invoice_id) == invoice
        reopened_events = BucketEventHistoryRepository(objects=profile.repository).load()
        assert_baseline_preserved(reopened_events)
        assert reopened_events.events.keys() - baseline_event_ids == set(created.bucket_event_ids)
        assert all(reopened_events.events[key].object_id == invoice.invoice_id for key in created.bucket_event_ids)
    assert not inside and trace.count("acknowledged") == 1
    assert trace.count("admitted") == (2 if conflict_once else 1)
    assert trace.count("definitive_no_write") == int(conflict_once)
