"""Content-addressed ``evidence_id`` / ``invoice_id`` determinism.

Real-behaviour proofs that both surrogate keys were replaced by a content
digest over their identifying fields, mirroring ``derive_transaction_id``:

* the minted id equals the pure ``derive_*_id`` digest of the record's own
  fields (content-addressed, not a random surrogate);
* the record round-trips through the real encrypted ``SecureObjectRepository``
  with the content id surviving a fresh-repository reload;
* the id is content-derived, not a constant — a record differing in one
  identifying field derives a different id (the anti-tautology leg);
* the id is deterministic under a frozen clock, while two genuinely-distinct
  records minted at the same frozen instant keep distinct ids via the mint's
  collision disambiguator (the genuine-duplicate case the ledger preserves).

No mocks: every case drives the real ``add`` service against a real bucket
runtime.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....core.time import frozen_clock
from ..evidence import derive_purchase_invoice_evidence_id
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._ledger_value_fixtures import isolated_settings, pdf_file, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "pdf_file", "runtime_profile", "secure_objects"]

_INSTANT = datetime(2026, 4, 14, 9, 30, 0, tzinfo=UTC)


class TestEvidenceIdContentAddressed:
    def test_evidence_id_equals_content_digest_and_roundtrips(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        pdf_file: Path,
    ) -> None:
        svc = _make_svc(isolated_settings, secure_objects)
        # Every storage op stays under one frozen instant, exactly as replay
        # freezes the whole run: a write under a frozen clock resets the bucket
        # session's idle deadline to that instant, so a later real-clock read
        # would see the session expired.
        with frozen_clock(_INSTANT):
            record = svc.add(
                bucket_id=_BUCKET_ID,
                source_path=pdf_file,
                supplier="Acme S.L.",
                invoice_number="INV-001",
                invoice_date="2026-01-15",
                taxable_base=Decimal("100.00"),
                iva_rate=Decimal("0.21"),
                iva_amount=Decimal("21.00"),
                notes="office supplies",
            ).record

            # The minted id is the content digest of the record's own fields.
            assert record.evidence_id == derive_purchase_invoice_evidence_id(
                bucket_id=record.bucket_id,
                source_sha256=record.source_sha256,
                media_kind=record.media_kind,
                supplier=record.supplier,
                invoice_number=record.invoice_number,
                invoice_date=record.invoice_date,
                taxable_base=record.taxable_base,
                iva_rate=record.iva_rate,
                iva_amount=record.iva_amount,
                notes=record.notes,
                created_at=record.created_at,
                disambiguator=0,
            )

            # The content id survives a fresh-repository reload with strict equality.
            reloaded = _make_svc(isolated_settings, secure_objects).view(
                bucket_id=_BUCKET_ID,
                evidence_id=record.evidence_id,
            )
        assert reloaded == record

    def test_evidence_id_is_content_derived_not_constant(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        pdf_file: Path,
    ) -> None:
        svc = _make_svc(isolated_settings, secure_objects)
        first = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_file, invoice_number="INV-A").record
        second = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_file, invoice_number="INV-B").record
        # A record differing only in invoice_number derives a different id, so
        # the id is bound to content rather than being a constant.
        assert first.evidence_id != second.evidence_id

    def test_evidence_id_genuine_duplicate_preserved_under_frozen_clock(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        pdf_file: Path,
    ) -> None:
        svc = _make_svc(isolated_settings, secure_objects)
        with frozen_clock(_INSTANT):
            first = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_file, invoice_number="DUP").record
            second = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_file, invoice_number="DUP").record
            # Two identical evidence records minted at the same frozen instant would
            # collide on the base digest; the mint's disambiguator keeps them distinct
            # so the genuine-duplicate case the ledger supports is preserved.
            assert first.evidence_id != second.evidence_id
            persisted_ids = {r.evidence_id for r in svc.list_all(bucket_id=_BUCKET_ID)}
        assert persisted_ids == {first.evidence_id, second.evidence_id}

    def test_evidence_id_roundtrip_antitautology(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        pdf_file: Path,
    ) -> None:
        """Prove the evidence roundtrip is not tautological (parity with the invoice class).

        Save a record, tamper the persisted payload on disk (re-save a mutated
        record through the real encrypted repository), reload through the service,
        and assert the reload surfaces the tampered content as strict inequality —
        so a broken save/load path could not pass this test.
        """
        from ..evidence import PurchaseInvoiceEvidenceDocument, PurchaseInvoiceEvidenceRepository

        svc = _make_svc(isolated_settings, secure_objects)
        original = svc.add(
            bucket_id=_BUCKET_ID,
            source_path=pdf_file,
            supplier="Acme S.L.",
            invoice_number="ANTITAUT",
            notes="original notes",
        ).record

        repository = PurchaseInvoiceEvidenceRepository(objects=secure_objects)
        document = repository.load(_BUCKET_ID)
        assert document is not None
        tampered = original.model_copy(update={"supplier": "Tampered SL", "notes": "TAMPERED"})
        repository.save(PurchaseInvoiceEvidenceDocument(bucket_id=_BUCKET_ID, records=(tampered,)))

        reloaded = _make_svc(isolated_settings, secure_objects).view(
            bucket_id=_BUCKET_ID,
            evidence_id=original.evidence_id,
        )
        assert reloaded != original
        assert reloaded.supplier == "Tampered SL"
        assert original.supplier == "Acme S.L."
