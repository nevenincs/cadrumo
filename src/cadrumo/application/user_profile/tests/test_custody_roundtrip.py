"""Persistence roundtrip for the generic secure-object custody carry.

Proves the previously-dropped per-bucket stores survive an export/import into a
recipient bucket with a *different* data-encryption key: the attachment evidence
bytes (FINANCIAL) and the bucket event-history audit trail are seeded in the
source bucket, carried under the full custody profile, restored into the
recipient bucket, and read back intact. The recipient bucket's distinct DEK is
the exact condition that breaks a digest-based carry, so a green test here is the
proof that the natural-key carry re-keys correctly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from cadrumo.application.user_profile.custody_carry import restore_carried_objects, serialize_carried_objects

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.storage.attachment import AttachmentStore
from ....domain.attachments import AttachmentNotFoundError
from ....domain.buckets import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from ....tests.aeat_literal_fixtures import aeat_url
from ....tests.secure_sql import isolated_two_bucket_runtime

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EVIDENCE_BYTES = b"%PDF-1.7 invoice evidence \x00\xff bytes"
_INSTANT = datetime(2026, 6, 30, 9, 0, 0, tzinfo=UTC)


def _seed_bucket_event(bucket_id: str) -> str:
    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=BucketEventType.BUCKET_EXPORTED,
        occurred_at=_INSTANT,
        actor="operator",
        object_type=BucketEventObjectType.BUCKET,
        object_id=bucket_id,
        payload={"transfer_id": "custody-roundtrip"},
    )
    event = BucketEvent(
        event_id=event_id,
        bucket_id=bucket_id,
        event_type=BucketEventType.BUCKET_EXPORTED,
        occurred_at=_INSTANT,
        actor="operator",
        object_type=BucketEventObjectType.BUCKET,
        object_id=bucket_id,
        payload_version=1,
        payload={"transfer_id": "custody-roundtrip"},
    )
    repo = BucketEventHistoryRepository()
    repo.save(BucketEventHistoryCatalogue(events={event_id: event}))
    return event_id


def test_structured_profile_excludes_attachment_evidence_bytes(tmp_path: Path) -> None:
    """The cleartext (structured) profile must not carry FINANCIAL attachment bytes."""
    from ....adapters.persistence.storage import StorageCustodyProfile

    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        AttachmentStore().put_bytes(_EVIDENCE_BYTES)
        _seed_bucket_event(runtime.primary.bucket_id)

        structured = serialize_carried_objects(
            bucket_id=runtime.primary.bucket_id,
            profile=StorageCustodyProfile.STRUCTURED,
        )
        full = serialize_carried_objects(
            bucket_id=runtime.primary.bucket_id,
            profile=StorageCustodyProfile.FULL,
        )

        structured_namespaces = {o.namespace for o in structured}
        full_namespaces = {o.namespace for o in full}
        # The full-custody-only FINANCIAL byte store is carried by the sealed
        # profile but never by the cleartext structured profile.
        assert "cadrumo.domain.attachments.blobs" in full_namespaces
        assert "cadrumo.domain.attachments.blobs" not in structured_namespaces


def _seed_attachment_manifest(sha: str) -> None:
    from ....domain.attachments import (
        Attachment,
        AttachmentKind,
        AttachmentSource,
    )

    AttachmentStore().write_manifest(
        Attachment(
            attachment_id=sha,
            kind=AttachmentKind.INVOICE_PDF,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="invoice.pdf",
            sha256=sha,
            mime_type="application/pdf",
            bytes_size=len(_EVIDENCE_BYTES),
            captured_at=_INSTANT,
        ),
    )


def _seed_justificante() -> str:

    from ....adapters.persistence.profile.justificante import JustificanteRepository
    from ....core import Period
    from ....domain.justificante import Justificante

    csv = "ABCD1234EFGH5678"
    justificante = Justificante(
        csv=csv,
        modelo="130",
        ejercicio="2025",
        period=Period.from_year_and_code(2025, "4T"),
        presented_at=_INSTANT,
        tax_id="12345678Z",
        total_a_ingresar=Decimal("100.00"),
        verification_url=AnyHttpUrl(aeat_url("sede", "/verifica")),
        source_pdf_path=Path("db://blobs") / ("a" * 64),
        source_pdf_sha256="a" * 64,
        parsed_at=_INSTANT,
    )
    JustificanteRepository().save(justificante)
    return csv


def test_full_custody_carry_restores_evidence_bytes_and_audit_trail(tmp_path: Path) -> None:
    from ....adapters.persistence.storage import StorageCustodyProfile

    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        source_bucket = runtime.primary.bucket_id
        target_bucket = runtime.secondary.bucket_id

        # Seed previously-dropped stores in the source bucket: an attachment blob
        # (byte store) AND its manifest (the manifest store strips attachment_id from
        # the payload, so this exercises the sha256-field manifest resolver), an audit
        # event (catalogue), and a justificante metadata record (bound-resolver path).
        sha = AttachmentStore().put_bytes(_EVIDENCE_BYTES)
        _seed_attachment_manifest(sha)
        event_id = _seed_bucket_event(source_bucket)
        justificante_csv = _seed_justificante()

        carried = serialize_carried_objects(bucket_id=source_bucket, profile=StorageCustodyProfile.FULL)

        carried_namespaces = {obj.namespace for obj in carried}
        assert "cadrumo.domain.attachments.blobs" in carried_namespaces
        assert "cadrumo.domain.buckets.event_history" in carried_namespaces
        assert "cadrumo.domain.justificante.metadata" in carried_namespaces

        with runtime.switch_to_secondary():
            # The recipient bucket starts without the evidence or the audit event.
            with pytest.raises(AttachmentNotFoundError):
                AttachmentStore().read_bytes(sha)

            restore_carried_objects(carried, target_bucket_id=target_bucket)

            # Evidence bytes survive and resolve under the recipient DEK.
            assert AttachmentStore().read_bytes(sha) == _EVIDENCE_BYTES
            # The manifest survives and re-keys under the recipient DEK (the
            # attachment_id, stripped from the payload, is re-injected on load).
            assert AttachmentStore().load_manifest(sha).sha256 == sha

            # The audit trail survives with its content-addressed event id intact.
            restored = BucketEventHistoryRepository().load()
            assert event_id in restored.events
            assert restored.events[event_id].payload["transfer_id"] == "custody-roundtrip"

            # The bound-resolver store survives and re-keys under the recipient DEK.
            from ....adapters.persistence.profile.justificante import JustificanteRepository

            assert JustificanteRepository().load(justificante_csv) is not None


def _seed_reconciliation_record(bucket_id: str) -> str:
    """Persist one grounded reconciliation record in the active bucket."""
    from ...modelo._reconciliation_records import (
        ModeloReconciliationAdvisory,
        ModeloReconciliationDiff,
        ModeloReconciliationDiffKind,
        ModeloReconciliationEvidenceKind,
        ModeloReconciliationRecord,
        ModeloReconciliationRecordRepository,
        ModeloReconciliationVerdict,
    )

    record = ModeloReconciliationRecord(
        bucket_event_id="e" * 64,
        bucket_id=bucket_id,
        work_unit_id="a1b2c3d4" * 8,
        source_kind=ModeloReconciliationEvidenceKind.DECLARATION,
        source_ref="/operator/evidence/modelo-100-declaracion.pdf",
        verdict=ModeloReconciliationVerdict.MISMATCHES,
        diffs=(
            ModeloReconciliationDiff(
                field_name="0604",
                work_unit_value="1234.56",
                evidence_value="1200.00",
                kind="casilla_value_mismatch",
                diff_kind=ModeloReconciliationDiffKind.CASILLA,
                legal_refs=("ley-35-2006:art-79",),
                source_refs=("aeat-manual-renta-2024",),
            ),
        ),
        advisories=(
            ModeloReconciliationAdvisory(
                code="totals_not_reconciled",
                message="filed totals were not reconciled",
                context={"reason": "no_persisted_revision"},
            ),
        ),
        actor="operator",
        reconciled_at=_INSTANT,
    )
    ModeloReconciliationRecordRepository().save(record)
    return record.bucket_event_id


def test_reconciliation_records_survive_the_custody_carry_with_grounding(tmp_path: Path) -> None:
    """A profile that has reconciled can be exported and restored.

    The namespace is registered at STRUCTURED_CUSTODY, which enrols it in the
    carried set, and the serialise path is fail-closed: a populated carried
    namespace with no natural-key resolver raises. So without a registered
    resolver, exporting the profile of ANY operator who had ever run a
    reconciliation raised — the store persisted fine and failed at the boundary
    that carries it.

    This drives the real defect rather than the gate that guards it: seed a
    record, serialise, restore into a recipient bucket whose DEK is different,
    and read it back. The distinct DEK is the condition that breaks a
    digest-based carry, so the natural key must be re-derived from the payload
    for this to pass — which is exactly what the bound resolver does, and why
    the composite key is no obstacle.
    """
    from ....adapters.persistence.storage import StorageCustodyProfile
    from ...modelo._reconciliation_records import (
        ModeloReconciliationRecordRepository,
        list_modelo_reconciliations,
    )

    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        source_bucket = runtime.primary.bucket_id
        target_bucket = runtime.secondary.bucket_id
        event_id = _seed_reconciliation_record(source_bucket)

        # Serialising must not raise, and must actually carry the namespace.
        carried = serialize_carried_objects(bucket_id=source_bucket, profile=StorageCustodyProfile.STRUCTURED)
        assert "cadrumo.modelo.reconciliation.records" in {obj.namespace for obj in carried}

        with runtime.switch_to_secondary():
            assert tuple(ModeloReconciliationRecordRepository().iter_records()) == ()

            restore_carried_objects(carried, target_bucket_id=target_bucket)

            restored = tuple(ModeloReconciliationRecordRepository().iter_records())
            assert len(restored) == 1
            assert restored[0].bucket_event_id == event_id
            # Grounding survives the re-key, through the public read API.
            entries = list_modelo_reconciliations(bucket_id=source_bucket)
            assert len(entries) == 1
            assert entries[0].diffs[0].legal_refs == ("ley-35-2006:art-79",)
            assert entries[0].diffs[0].source_refs == ("aeat-manual-renta-2024",)
            # Advisories survive too, read off the restored record itself.
            assert restored[0].advisories[0].context == {"reason": "no_persisted_revision"}
