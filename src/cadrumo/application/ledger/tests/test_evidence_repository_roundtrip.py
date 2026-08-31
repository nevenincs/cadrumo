"""Encrypted-boundary roundtrip for the purchase-invoice evidence catalogue.

``PurchaseInvoiceEvidence`` is a persisted record: it rides an encrypted
:class:`~adapters.persistence.storage.Envelope` in the bucket-local
``LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE`` through
:class:`~application.ledger.evidence.PurchaseInvoiceEvidenceRepository`. The catalogue had
save/load coverage that only asserted records survived, never that they survived
*unchanged*, so a save-drops-field / load-re-defaults-field regression on any of
the seven optional fiscal fields was invisible.

These are the two gates ``aeat-quality-gates`` requires of that boundary:
a real save -> load -> strict-equality cycle with every defaultable field carrying
a NON-default value, and an anti-tautology proof that surgically rewrites the
stored payload and asserts the load refuses it. Real adapters throughout -- real
key provider, real SQLite engine, real serializer. No mocks.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ._ledger_value_fixtures import secure_objects

__all__ = ["secure_objects"]
from pydantic import ValidationError

from ....adapters.persistence.storage.secure_object_namespaces import LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.classification.policies import SensitivityClass
from ..evidence import (
    MediaKind,
    PurchaseInvoiceEvidence,
    PurchaseInvoiceEvidenceDocument,
    PurchaseInvoiceEvidenceRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "34343434-3434-4434-8434-343434343434"
runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")
_DIGEST = "b" * 64
_CREATED_AT = datetime(2026, 2, 5, 9, 30, tzinfo=UTC)
_UPDATED_AT = datetime(2026, 3, 11, 17, 45, tzinfo=UTC)


def _fully_populated_record() -> PurchaseInvoiceEvidence:
    """Build a record whose every defaultable field carries a non-default value.

    ``supplier``, ``invoice_number``, ``invoice_date``, ``taxable_base``,
    ``iva_rate``, ``iva_amount`` all default to ``None`` and ``notes`` to ``""``;
    a fixture leaving them at their defaults cannot detect a field dropped on save
    and silently re-defaulted on load, which is the regression this pins.
    """
    return PurchaseInvoiceEvidence(
        evidence_id="ev-roundtrip-01",
        bucket_id=_BUCKET_ID,
        source_path="facturas/2026/proveedor-acme.pdf",
        source_sha256=_DIGEST,
        attachment_id=_DIGEST,
        media_kind=MediaKind.IMAGE,
        supplier="Acme Suministros SL",
        invoice_number="2026-0142",
        invoice_date="2026-02-05",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
        notes="operator annotation that must survive the cycle",
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )


def test_evidence_record_roundtrips_through_encrypted_storage(secure_objects: SecureObjectRepository) -> None:
    """Save, load through a FRESH handle, assert strict model equality."""
    original = _fully_populated_record()
    PurchaseInvoiceEvidenceRepository(objects=secure_objects).save(
        PurchaseInvoiceEvidenceDocument(bucket_id=_BUCKET_ID, records=(original,)),
    )

    # A fresh repository handle: the record is genuinely re-read from storage,
    # not returned from anything the writing handle still held in memory.
    document = PurchaseInvoiceEvidenceRepository(objects=secure_objects).load(_BUCKET_ID)

    assert document is not None
    assert document.records == (original,)
    loaded = document.records[0]
    assert loaded == original
    # Spot-check the axes a re-default would silently reset: the Decimals keep
    # their exact quantisation, and the two timestamps stay distinct.
    assert loaded.taxable_base == Decimal("100.00")
    assert loaded.iva_amount == Decimal("21.00")
    assert loaded.notes == "operator annotation that must survive the cycle"
    assert loaded.created_at == _CREATED_AT
    assert loaded.updated_at == _UPDATED_AT


def test_persisted_record_stripped_of_attachment_id_is_refused_at_load(
    secure_objects: SecureObjectRepository,
) -> None:
    """Anti-tautology proof: delete the field from the stored payload and reload.

    ``attachment_id`` is the record's in-store byte home and is required, so a
    persisted record without it must not load. Persist a valid record, surgically
    remove the field from the decrypted envelope, re-save, and assert the real
    load path refuses. If this ever passed with the field absent, the
    required-field contract would be unenforced at the encrypted boundary and the
    roundtrip above would be worthless.
    """
    original = _fully_populated_record()
    repository = PurchaseInvoiceEvidenceRepository(objects=secure_objects)
    repository.save(PurchaseInvoiceEvidenceDocument(bucket_id=_BUCKET_ID, records=(original,)))

    record = secure_objects.load(
        LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE.namespace,
        _BUCKET_ID,
        expected_class=SensitivityClass.FINANCIAL,
        max_supported_version=LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE.schema_version,
    )
    assert record is not None
    envelope = json.loads(record.payload.decode("utf-8"))
    stored = envelope["payload"]["records"][0]
    assert stored["attachment_id"] == _DIGEST, "fixture must serialise attachment_id for this proof to mean anything"

    def _rewrite(payload: dict[str, object]) -> None:
        secure_objects.save(
            namespace=LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE.namespace,
            object_key=_BUCKET_ID,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=json.dumps(payload).encode("utf-8"),
        )

    # Control: re-saving the UNMODIFIED envelope through the same decode/encode
    # surgery must still load. Without this, a refusal below could come from the
    # surgery itself rather than from the missing field, and the proof would pass
    # for the wrong reason.
    _rewrite(envelope)
    assert PurchaseInvoiceEvidenceRepository(objects=secure_objects).load(_BUCKET_ID) is not None

    del stored["attachment_id"]
    _rewrite(envelope)

    with pytest.raises(ValidationError):
        PurchaseInvoiceEvidenceRepository(objects=secure_objects).load(_BUCKET_ID)
