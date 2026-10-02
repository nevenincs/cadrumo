"""Actual custody ingestor checks planned identity against its single byte read."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, override

import pytest

from .....application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from .....application.ledger.evidence_ports import EvidenceAttachmentIngestRequest
from .....core.hashing import sha256_hex
from .....core.time.clock import now
from .....domain.attachments.models import Attachment
from ...storage.attachment import AttachmentStore
from ..purchase_invoice_evidence import LedgerEvidenceAttachmentIngestor

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


class ObservedStore(AttachmentStore):
    """Detect custody entry without composing any native or encrypted backend."""

    observed_bytes: ClassVar[list[bytes]] = []
    observed_manifests: ClassVar[list[Attachment]] = []

    @override
    def put_bytes(self, data: bytes) -> str:
        """Capture exactly the bytes handed to canonical attachment custody."""
        self.observed_bytes.append(data)
        return sha256_hex(data)

    @override
    def write_manifest(self, attachment: Attachment) -> None:
        """Capture the canonical prepared manifest without a native write."""
        self.observed_manifests.append(attachment)


@pytest.mark.parametrize("matches", [True, False])
def test_actual_ingestor_reads_once_and_refuses_changed_identity_before_custody(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    matches: bool,
) -> None:
    """The digest must describe the same allocation passed into attachment storage."""
    data = b"%PDF-synthetic\x00\xff"
    source = tmp_path / "invoice.pdf"
    source.write_bytes(data)
    reads: list[Path] = []
    original_read = Path.read_bytes

    def read(path: Path) -> bytes:
        reads.append(path)
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    ObservedStore.observed_bytes = []
    ObservedStore.observed_manifests = []
    store = ObservedStore(bucket_id="22222222-2222-4222-8222-222222222222")
    ingestor = LedgerEvidenceAttachmentIngestor(store=store)
    request = EvidenceAttachmentIngestRequest(
        bucket_id=store.bucket_id or "",
        source_path=source,
        media_kind="pdf",
        mime_type="application/pdf",
        captured_at=now(),
        actor="synthetic",
        expected_content_digest=sha256_hex(data) if matches else "0" * 64,
    )
    if matches:
        assert ingestor.ingest(request) == sha256_hex(data)
        assert ObservedStore.observed_bytes == [data]
        assert ObservedStore.observed_manifests[0].source_reference == str(source)
    else:
        with pytest.raises(PurchaseInvoiceEvidenceInputError):
            ingestor.ingest(request)
        assert not ObservedStore.observed_bytes and not ObservedStore.observed_manifests
    assert reads == [source]
