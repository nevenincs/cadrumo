"""A bucket's invoice surfaces never return a document filed under another key.

Both catalogues derive their secure-object key from the payload's own identity:
:class:`~application.ledger.PurchaseInvoiceEvidenceRepository` keys on the
document's ``bucket_id``, and
:class:`~application.ledger.BusinessOperationInvoiceRepository` keys on the
composite ``bucket_id:source_kind``. The stored key and the decrypted document
are therefore two encodings of one fact, and a valid document for bucket B
placed under A's key would leak B's invoices into A's ledger surface.

The guard is the shared ``SecureBoundRepository`` load contract, which compares
the identity rebuilt from the decrypted payload against the key that was
requested. These are the per-repository regressions against that contract --
deliberately NOT a second guard at either subclass. Both services read through
``load``, so both list surfaces inherit the refusal.

Real encrypted SQLite, real key provider, real serializer. No mocks. Each test
pairs its refusal with the same-bucket round trip, so a guard that refused
everything would fail here rather than pass.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.storage import SecureObjectRowIdentityError
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._business_operation_invoice import (
    BusinessOperationInvoice,
    BusinessOperationInvoiceDirection,
    BusinessOperationInvoiceDocument,
    BusinessOperationInvoiceRepository,
)
from .._evidence import (
    MediaKind,
    PurchaseInvoiceEvidence,
    PurchaseInvoiceEvidenceDocument,
    PurchaseInvoiceEvidenceRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_A = "34343434-3434-4434-8434-343434343434"
_BUCKET_B = "35353535-3535-4535-8535-353535353535"
_DIGEST = "b" * 64
_AT = datetime(2026, 2, 5, 9, 30, tzinfo=UTC)


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_A) as profile:
        yield profile


@pytest.fixture
def secure_objects(runtime_profile: TestRuntimeProfile) -> SecureObjectRepository:
    return runtime_profile.repository


# ---------------------------------------------------------------------------
# Purchase-invoice evidence: key is the document's own bucket_id
# ---------------------------------------------------------------------------


def _evidence_document(bucket_id: str) -> PurchaseInvoiceEvidenceDocument:
    return PurchaseInvoiceEvidenceDocument(
        bucket_id=bucket_id,
        records=(
            PurchaseInvoiceEvidence(
                evidence_id="ev-row-identity-01",
                bucket_id=bucket_id,
                source_path="facturas/2026/proveedor-acme.pdf",
                source_sha256=_DIGEST,
                attachment_id=_DIGEST,
                media_kind=MediaKind.IMAGE,
                created_at=_AT,
                updated_at=_AT,
            ),
        ),
    )


def test_evidence_document_round_trips_under_its_own_key(secure_objects: SecureObjectRepository) -> None:
    """Positive control: the same-bucket document must still load."""
    repository = PurchaseInvoiceEvidenceRepository(objects=secure_objects)
    original = _evidence_document(_BUCKET_A)
    repository.save(original)

    assert PurchaseInvoiceEvidenceRepository(objects=secure_objects).load(_BUCKET_A) == original


def test_evidence_document_for_a_foreign_bucket_is_refused(secure_objects: SecureObjectRepository) -> None:
    """A valid bucket-B document stored under A's key must not surface for A.

    Written through the raw secure-object store rather than ``save``: the
    write path already refuses a foreign document, so the misfiled row can
    only be produced by going under it -- which is exactly the state the read
    guard exists to catch.
    """
    repository = PurchaseInvoiceEvidenceRepository(objects=secure_objects)
    foreign = _evidence_document(_BUCKET_B)
    write = repository.to_secure_object_write(foreign)
    secure_objects.save(
        namespace=write.namespace,
        object_key=_BUCKET_A,
        classification=write.classification,
        schema_version=write.schema_version,
        written_at=write.written_at,
        payload=write.payload,
    )

    # Non-vacuity: the row is present and decrypts cleanly under A's key, so the
    # refusal below is the identity guard firing, not an unreadable row.
    stored = secure_objects.load(
        write.namespace,
        _BUCKET_A,
        expected_class=write.classification,
        max_supported_version=write.schema_version,
    )
    assert stored is not None
    assert _BUCKET_B.encode() in stored.payload

    with pytest.raises(SecureObjectRowIdentityError):
        PurchaseInvoiceEvidenceRepository(objects=secure_objects).load(_BUCKET_A)


# ---------------------------------------------------------------------------
# Business-operation invoices: key is the composite bucket_id:source_kind
# ---------------------------------------------------------------------------


def _invoice_document(
    bucket_id: str,
    kind: BusinessOperationInvoiceDirection,
) -> BusinessOperationInvoiceDocument:
    return BusinessOperationInvoiceDocument(
        bucket_id=bucket_id,
        source_kind=kind,
        records=(
            BusinessOperationInvoice(
                invoice_id="inv-row-identity-01",
                bucket_id=bucket_id,
                source_kind=kind,
                counterparty_nif="B12345674",
                counterparty_name="Acme Suministros SL",
                invoice_number="2026-0142",
                invoice_date="2026-02-05",
                country_code=None,
                eu_iva_id=None,
                operation_type=None,
                created_at=_AT,
                updated_at=_AT,
            ),
        ),
    )


@pytest.mark.parametrize(
    "kind",
    [BusinessOperationInvoiceDirection.PAYABLE_INVOICE, BusinessOperationInvoiceDirection.COLLECTIBLE_INVOICE],
)
def test_invoice_document_round_trips_under_its_own_composite_key(
    secure_objects: SecureObjectRepository,
    kind: BusinessOperationInvoiceDirection,
) -> None:
    """Positive control, both directions: the same-bucket catalogue must still load."""
    repository = BusinessOperationInvoiceRepository(objects=secure_objects)
    original = _invoice_document(_BUCKET_A, kind)
    repository.save(original)
    key = repository.extract_identifier(original)

    assert BusinessOperationInvoiceRepository(objects=secure_objects).load(key) == original


@pytest.mark.parametrize(
    "kind",
    [BusinessOperationInvoiceDirection.PAYABLE_INVOICE, BusinessOperationInvoiceDirection.COLLECTIBLE_INVOICE],
)
def test_invoice_document_for_a_foreign_bucket_is_refused(
    secure_objects: SecureObjectRepository,
    kind: BusinessOperationInvoiceDirection,
) -> None:
    """A valid bucket-B catalogue placed under A's composite key must not surface."""
    repository = BusinessOperationInvoiceRepository(objects=secure_objects)
    foreign = _invoice_document(_BUCKET_B, kind)
    write = repository.to_secure_object_write(foreign)
    a_key = repository.extract_identifier(_invoice_document(_BUCKET_A, kind))
    secure_objects.save(
        namespace=write.namespace,
        object_key=a_key,
        classification=write.classification,
        schema_version=write.schema_version,
        written_at=write.written_at,
        payload=write.payload,
    )

    # Non-vacuity: the row decrypts cleanly under A's composite key, so the
    # refusal below is the identity guard firing, not an unreadable row.
    stored = secure_objects.load(
        write.namespace,
        a_key,
        expected_class=write.classification,
        max_supported_version=write.schema_version,
    )
    assert stored is not None
    assert _BUCKET_B.encode() in stored.payload

    with pytest.raises(SecureObjectRowIdentityError):
        BusinessOperationInvoiceRepository(objects=secure_objects).load(a_key)


def test_the_two_directions_do_not_share_a_key(secure_objects: SecureObjectRepository) -> None:
    """The composite key must separate payable from collectible within one bucket.

    If ``source_kind`` dropped out of the key the two catalogues would collide
    on ``bucket_id`` alone, and the identity guard could not tell them apart.
    """
    repository = BusinessOperationInvoiceRepository(objects=secure_objects)

    payable_key = repository.extract_identifier(
        _invoice_document(_BUCKET_A, BusinessOperationInvoiceDirection.PAYABLE_INVOICE),
    )
    collectible_key = repository.extract_identifier(
        _invoice_document(_BUCKET_A, BusinessOperationInvoiceDirection.COLLECTIBLE_INVOICE),
    )

    assert payable_key != collectible_key
    assert payable_key.startswith(_BUCKET_A)
    assert collectible_key.startswith(_BUCKET_A)
