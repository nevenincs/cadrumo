"""Intake composition delegates canonical custody/FX with lazy admission."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.invoices.bulk_import import import_invoices_from_rows, read_bulk_invoice_import_source
from ...application.invoices.creation_wizard import create_invoice_via_wizard
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...core.hashing import canonical_json_bytes, sha256_hex
from ...domain.buckets.event import BucketEventHistoryCatalogue, BucketEventType
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.iva.classification import InvoiceKind
from ..invoice_intake_operation_composition import build_invoice_intake_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_PROFILE = UUID("76767676-7676-4767-8676-767676767676")


def test_composed_wizard_and_book_use_retained_pin_and_reopen_canonical_encrypted_audit(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ...domain.calculations.registry import authority

    # Both services must use the retained pin; the standalone fallback remains
    # available to ordinary callers, but is not a worker's generation lease.
    def fallback():
        pytest.fail("worker intake acquired a new descriptor-following authority")

    monkeypatch.setattr(authority, "bundled_indexed_authority", fallback)
    admissions: list[str] = []
    commits = 0

    def commit(save: Callable[[], None]) -> None:
        nonlocal commits
        save()
        commits += 1

    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile,
        validating_governed_facts(authority_operation),
    ):
        baseline_events = BucketEventHistoryRepository(objects=profile.repository).load()
        baseline_event_ids = frozenset(baseline_events.events)
        baseline_event_digest = sha256_hex(canonical_json_bytes(baseline_events.model_dump(mode="json")))
        ports = build_invoice_intake_ports(
            profile_id=_PROFILE,
            operation=authority_operation,
            commit=commit,
            admit_provider=lambda: admissions.append("provider"),
        )
        assert ports.profile_id == _PROFILE and ports.operation is authority_operation and not admissions
        with pytest.raises(ProfileAccessRefusedError):
            build_invoice_intake_ports(
                profile_id=uuid4(),
                operation=authority_operation,
                commit=commit,
                admit_provider=lambda: admissions.append("foreign"),
            )
        creation = ports.creation()
        wizard = create_invoice_via_wizard(
            bucket_id=str(_PROFILE),
            kind=InvoiceKind.RECEIVED,
            counterparty_nif="A58818501",
            counterparty_name="Synthetic supplier",
            invoice_number="PIN-WIZARD",
            invoice_date="2026-05-01",
            taxable_base="100.00",
            iva_rate="21",
            currency="EUR",
            country_code="ES",
            series="S",
            recargo_amount="5.20",
            ports=creation,
            operation=authority_operation,
        )
        path = tmp_path / "synthetic.csv"
        payload = b"counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate\nA58818501,Supplier,PIN-BOOK,2026-05-01,100.00,21\n"
        path.write_bytes(payload)
        source = read_bulk_invoice_import_source(path, mapper=ports.mapper, expected_sha256=sha256_hex(payload))
        imported = import_invoices_from_rows(
            source,
            bucket_id=str(_PROFILE),
            kind=InvoiceKind.RECEIVED,
            declared_country="ES",
            ports=creation,
            operation=authority_operation,
        )
        assert not wizard.already_existed and imported.created == 1 and commits == 2
        reopened = InvoiceCatalogueRepository(objects=profile.repository).load()
        assert reopened.get(wizard.invoice.invoice_id) == wizard.invoice
        assert reopened.get(imported.created_invoice_ids[0]) is not None
        reopened_events = BucketEventHistoryRepository(objects=profile.repository).load()
        assert baseline_event_ids <= reopened_events.events.keys()
        retained = BucketEventHistoryCatalogue(events={key: reopened_events.events[key] for key in baseline_event_ids})
        assert sha256_hex(canonical_json_bytes(retained.model_dump(mode="json"))) == baseline_event_digest
        new_events = tuple(reopened_events.events[key] for key in reopened_events.events.keys() - baseline_event_ids)
        assert len(new_events) == 2
        assert {event.object_id for event in new_events} == {wizard.invoice.invoice_id, *imported.created_invoice_ids}
        assert all(event.event_type is BucketEventType.PAYABLE_INVOICE_CREATED for event in new_events)
    assert admissions == ["provider"]
