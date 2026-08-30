"""Regression: the attachment evidence path can write only byte-bearing manifests.

There is no link-only ``add_link_attachment`` path that records a
Gmail/Drive/URL reference as a ``text/uri-list`` manifest without ever
fetching the document. This gate proves the invariant: every manifest the
byte-bearing
:func:`cadrumo.domain.attachments.add_attachment` path writes carries the
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
from ..enums import AttachmentKind, AttachmentSource
from ..errors import AttachmentValidationError
from ..models import Attachment
from ..service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CAPTURED_AT = datetime(2026, 6, 30, 9, 0, 0, tzinfo=UTC)


# The store refuses a manifest from another profile bucket, so the fixture
# names the same bucket the runtime profile provisions.
_BUCKET_ID = "3a1f0b2c-4d5e-4f60-8a71-92b3c4d5e6f7"


def _add_drive_document(
    store: AttachmentStore,
    *,
    data: bytes,
    source_reference: str,
    mime_type: str = "application/pdf",
    bucket_id: str | None = None,
    link_transaction_ids: tuple[str, ...] = (),
    metadata: dict[str, str] | None = None,
) -> Attachment:
    return add_attachment(
        store,
        content=AttachmentBytesContent(data=data),
        request=AttachmentIngestionRequest(
            kind=AttachmentKind.DRIVE_DOCUMENT,
            source=AttachmentSource.GOOGLE_DRIVE,
            source_reference=source_reference,
            mime_type=mime_type,
            captured_at=_CAPTURED_AT,
            bucket_id=bucket_id,
            link_transaction_ids=link_transaction_ids,
            metadata=metadata or {},
        ),
    )


def test_add_attachment_writes_byte_bearing_manifest_never_uri_list(tmp_path: Path) -> None:
    """A fetched document is stored with its real digest and mime, not as a link."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = AttachmentStore()
        data = b"%PDF-1.4\n%fetched-drive-invoice\n" + b"\x00" * 32
        reference = "https://drive.google.com/file/d/ABC123ticket/view"

        attachment = _add_drive_document(
            store,
            data=data,
            source_reference=reference,
            bucket_id=_BUCKET_ID,
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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = AttachmentStore()
        for index in range(3):
            data = f"document-{index}".encode() + b"\x00payload"
            _add_drive_document(
                store,
                data=data,
                source_reference=f"https://drive.google.com/file/d/doc{index}/view",
                mime_type="application/octet-stream",
            )

        manifests = tuple(store.iter_manifests())
        assert manifests, "expected the byte path to have written manifests"
        assert all(manifest.mime_type != "text/uri-list" for manifest in manifests)


def test_attachment_store_refuses_link_only_uri_list_manifest(tmp_path: Path) -> None:
    """Even a tampered manifest object cannot write a link-only URI-list record."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = AttachmentStore()
        attachment = _add_drive_document(
            store,
            data=b"%PDF-1.4\nvalid-byte-bearing-document\n",
            source_reference="https://drive.google.com/file/d/bytebearing/view",
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


def test_parameterized_uri_list_mime_is_refused_at_both_boundaries(tmp_path: Path) -> None:
    """A parameter section must not smuggle a link-only media type past the guards.

    MIME syntax allows ``type/subtype; param=value``; a full-string equality
    check accepted ``text/uri-list; charset=utf-8``. Both the model validator
    and the store write guard must compare the parsed media type.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = AttachmentStore()
        attachment = _add_drive_document(
            store,
            data=b"%PDF-1.4\nbyte-bearing-document-for-param-variants\n",
            source_reference="https://drive.google.com/file/d/parammime/view",
        )

        for disguised_mime in (
            "text/uri-list; charset=utf-8",
            "text/uri-list;charset=us-ascii",
            "TEXT/URI-LIST; q=0.9",
            "text/uri-list ; boundary=x",
        ):
            manifest_payload = attachment.model_dump(mode="python")
            manifest_payload["mime_type"] = disguised_mime
            with pytest.raises(ValidationError, match="link-only URI list"):
                Attachment.model_validate(manifest_payload)

            tampered = attachment.model_copy(update={"mime_type": disguised_mime})
            with pytest.raises(AttachmentValidationError, match="link-only URI list"):
                store.write_manifest(tampered)

        # A parameterized NON-link media type stays accepted: the guard parses
        # the media type, it does not blanket-refuse parameter sections.
        parameterized_ok = attachment.model_dump(mode="python")
        parameterized_ok["mime_type"] = "text/plain; charset=utf-8"
        revalidated = Attachment.model_validate(parameterized_ok)
        assert revalidated.mime_type == "text/plain; charset=utf-8"

        loaded = store.load_manifest(attachment.attachment_id)
        assert loaded.mime_type == "application/pdf"
