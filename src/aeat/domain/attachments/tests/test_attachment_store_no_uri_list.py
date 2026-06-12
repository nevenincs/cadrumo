"""Regression: the attachment evidence path can write only byte-bearing manifests.

The C2 ledger-evidence campaign deleted the link-only ``add_link_attachment``
path that recorded a Gmail/Drive/URL reference as a ``text/uri-list`` manifest
without ever fetching the document. This gate proves the invariant the deletion
established: every manifest the byte-bearing
:func:`aeat.domain.attachments.add_attachment_bytes` path writes carries the
real ``sha256`` of the stored bytes and a concrete document ``mime_type`` — never
``text/uri-list`` — over a real SQLite-backed :class:`AttachmentStore`.

Real active-profile runtime, real SQLite, no mocks. If a link-only manifest
path is ever reintroduced this gate reds.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage.attachment import AttachmentStore
from ....tests.secure_sql import isolated_runtime_profile
from .._enums import AttachmentKind, AttachmentSource
from .._errors import AttachmentValidationError
from .._models import Attachment
from .._service import add_attachment_bytes

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_add_attachment_bytes_writes_byte_bearing_manifest_never_uri_list(tmp_path: Path) -> None:
    """A fetched document is stored with its real digest and mime, not as a link."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        store = AttachmentStore()
        data = b"%PDF-1.4\n%fetched-drive-invoice\n" + b"\x00" * 32
        reference = "https://drive.google.com/file/d/ABC123ticket/view"

        attachment = add_attachment_bytes(
            store,
            data=data,
            kind=AttachmentKind.DRIVE_DOCUMENT,
            source=AttachmentSource.GOOGLE_DRIVE,
            source_reference=reference,
            mime_type="application/pdf",
            captured_at=datetime.now(UTC).replace(microsecond=0),
            bucket_id="b" * 32,
            link_transaction_ids=("tx-evidence-1",),
            metadata={"source": "GOOGLE_DRIVE", "source_reference": reference},
        )

        # The stored manifest carries the REAL content digest and document mime.
        assert attachment.sha256 == hashlib.sha256(data).hexdigest()
        assert attachment.attachment_id == attachment.sha256
        assert attachment.mime_type == "application/pdf"
        assert attachment.mime_type != "text/uri-list"
        assert attachment.bytes_size == len(data)
        # The link is kept only as provenance metadata, never as the payload.
        assert attachment.source_reference == reference
        assert attachment.metadata["source_reference"] == reference

        # The persisted manifest read back is byte-bearing: the stored blob is the
        # document bytes, and the manifest mime is the document mime.
        loaded = store.load_manifest(attachment.attachment_id)
        assert loaded.mime_type == "application/pdf"
        assert store.read_bytes(attachment.attachment_id) == data


def test_no_manifest_in_the_store_carries_a_uri_list_mime(tmp_path: Path) -> None:
    """Sweep every manifest the byte path can write: none is a link-only record."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        store = AttachmentStore()
        for index in range(3):
            data = f"document-{index}".encode() + b"\x00payload"
            add_attachment_bytes(
                store,
                data=data,
                kind=AttachmentKind.DRIVE_DOCUMENT,
                source=AttachmentSource.GOOGLE_DRIVE,
                source_reference=f"https://drive.google.com/file/d/doc{index}/view",
                mime_type="application/octet-stream",
                captured_at=datetime.now(UTC).replace(microsecond=0),
            )

        manifests = tuple(store.iter_manifests())
        assert manifests, "expected the byte path to have written manifests"
        assert all(manifest.mime_type != "text/uri-list" for manifest in manifests)


def test_attachment_store_refuses_link_only_uri_list_manifest(tmp_path: Path) -> None:
    """Even a tampered manifest object cannot write a link-only URI-list record."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        store = AttachmentStore()
        attachment = add_attachment_bytes(
            store,
            data=b"%PDF-1.4\nvalid-byte-bearing-document\n",
            kind=AttachmentKind.DRIVE_DOCUMENT,
            source=AttachmentSource.GOOGLE_DRIVE,
            source_reference="https://drive.google.com/file/d/bytebearing/view",
            mime_type="application/pdf",
            captured_at=datetime.now(UTC).replace(microsecond=0),
        )

        manifest_payload = attachment.model_dump(mode="python")
        manifest_payload["mime_type"] = "text/uri-list"
        with pytest.raises(ValidationError, match="link-only URI list"):
            Attachment.model_validate(manifest_payload)

        tampered = attachment.model_copy(update={"mime_type": "text/uri-list"})
        with pytest.raises(AttachmentValidationError, match="link-only URI list"):
            store.write_manifest(tampered)

        loaded = store.load_manifest(attachment.attachment_id)
        assert loaded.mime_type == "application/pdf"
