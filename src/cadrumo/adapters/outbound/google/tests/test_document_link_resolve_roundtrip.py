"""Fetch-and-encrypt roundtrip for the repurposed ledger doclink path.

``aeat app ledger doclink`` resolves a
Drive document link to its bytes and stores those bytes as encrypted evidence —
never a link. This gate exercises that end to end with the storage and manifest
path REAL (a real ``AttachmentStore`` over real SQLite) and the Drive media
request executed through a real ``google-api-python-client`` resource pointed at
a local HTTP endpoint:

* the fetched bytes equal the stored bytes, and the persisted manifest's
  ``sha256`` / ``mime_type`` match (the fetch-and-encrypt roundtrip);
* mutating the on-disk blob after a successful store makes the store's re-hash
  verification raise rather than returning the mutated content
  (anti-tautology);
* a Gmail reference and an arbitrary URL each refuse with the typed
  scope-named error and write nothing to the store (the refusal contract).

No mocks of the storage or manifest path: a regression in the byte custody,
the digest pinning, or the refusal contract surfaces as a real failure.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....adapters.persistence.storage.attachment import AttachmentStore
from .....domain.attachments.enums import AttachmentKind, AttachmentSource
from .....domain.attachments.errors import AttachmentValidationError
from .....domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from .....tests.secure_sql import isolated_runtime_profile
from ...storage import OutboundStoragePermissionError
from ..document_link_resolver import resolve_document_link
from .drive_media_server import drive_media_endpoint

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

# The attachment store refuses a manifest naming another profile bucket, so
# the fixture names the same bucket the runtime profile provisions.
_BUCKET_ID = "9d4e1a2b-6c70-4f81-8b92-a3c4d5e6f701"

_FILE_ID = "1AbcDEfgHIjkLMnoPQRstuVWxyz12345"
_DRIVE_LINK = f"https://drive.google.com/file/d/{_FILE_ID}/view"
_CAPTURED_AT = datetime(2026, 5, 28, 12, 45, 0, tzinfo=UTC)


def _store_resolved_link(store: AttachmentStore, *, payload: bytes):
    """Resolve a Drive link through the Google client and store the fetched bytes."""
    with drive_media_endpoint(payload=payload) as endpoint:
        data = resolve_document_link(
            source=AttachmentSource.GOOGLE_DRIVE,
            reference=_DRIVE_LINK,
            credentials=None,
            service=endpoint.service,
        )
        assert endpoint.requested_paths == [f"/drive/v3/files/{_FILE_ID}?alt=media"]
    return add_attachment(
        store,
        content=AttachmentBytesContent(data=data),
        request=AttachmentIngestionRequest(
            kind=AttachmentKind.DRIVE_DOCUMENT,
            source=AttachmentSource.GOOGLE_DRIVE,
            source_reference=_DRIVE_LINK,
            mime_type="application/pdf",
            captured_at=_CAPTURED_AT,
            bucket_id=_BUCKET_ID,
            link_transaction_ids=("tx-doclink-1",),
            metadata={"source": "GOOGLE_DRIVE", "source_reference": _DRIVE_LINK},
        ),
    )


def test_fetch_and_encrypt_roundtrip_stores_fetched_bytes(tmp_path: Path) -> None:
    """Drive bytes resolved through the seam are stored byte-identically."""
    payload = b"%PDF-1.4\n%resolved-drive-justificante\n" + b"\x01" * 48
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = AttachmentStore()
        attachment = _store_resolved_link(store, payload=payload)

        # Manifest digest and mime match the fetched bytes.
        assert attachment.sha256 == hashlib.sha256(payload).hexdigest()
        assert attachment.attachment_id == attachment.sha256
        assert attachment.mime_type == "application/pdf"
        assert attachment.bytes_size == len(payload)

        # Stored bytes equal the fetched bytes; the persisted manifest agrees.
        assert store.read_bytes(attachment.attachment_id) == payload
        loaded = store.load_manifest(attachment.attachment_id)
        assert loaded.sha256 == hashlib.sha256(payload).hexdigest()
        assert loaded.mime_type == "application/pdf"
        assert loaded.source_reference == _DRIVE_LINK
        store.verify_blob(attachment.attachment_id)


def test_blob_mutation_after_store_surfaces_on_reverify(tmp_path: Path) -> None:
    """Anti-tautology: corrupt the on-disk blob; re-hash verification must raise.

    If this passes silently with the blob mutated, the byte-custody guarantee is
    tautological — the stored bytes no longer prove the manifest's content.
    """
    from sqlalchemy import select

    from .....adapters.persistence.storage.sql.engine import get_engine
    from .....adapters.persistence.storage.sql.session import session_scope
    from ....persistence.storage.crypto.encrypted_columns import (
        decrypt_secure_object_payload,
        encrypt_secure_object_payload,
        secure_object_payload_aad,
    )
    from ....persistence.storage.sql import SecureObjectRow

    payload = b"%PDF-1.4 anti-tautology blob mutation proof payload"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        store = AttachmentStore()
        attachment = _store_resolved_link(store, payload=payload)
        # Baseline: the freshly-stored blob verifies.
        store.verify_blob(attachment.attachment_id)

        # Corrupt the blob CONTENT under the row's own AAD. The AAD binds the row
        # identity (namespace, object_key, schema_version), so re-encrypting the
        # mutated plaintext under that same AAD keeps AEAD/AAD verification passing
        # and surfaces the mutation at the re-hash layer (the byte-custody check)
        # rather than the decryption layer — exactly the guarantee under test.
        engine = get_engine(profile.settings)
        with session_scope(engine) as session:
            target_row = session.execute(
                select(SecureObjectRow).where(
                    SecureObjectRow.namespace == "cadrumo.domain.attachments.blobs",
                    SecureObjectRow.object_key == attachment.attachment_id,
                ),
            ).scalar_one()
            target_aad = secure_object_payload_aad(
                target_row.namespace,
                bytes(target_row.object_key),
                target_row.schema_version,
            )
            decrypted = decrypt_secure_object_payload(bytes(target_row.payload), associated_data=target_aad)
            target_row.payload = encrypt_secure_object_payload(decrypted + b"-tampered", associated_data=target_aad)

        with pytest.raises(AttachmentValidationError):
            store.verify_blob(attachment.attachment_id)


def test_gmail_reference_refuses_and_writes_nothing(tmp_path: Path) -> None:
    """A Gmail link refuses with the scope error and stores no manifest/blob."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = AttachmentStore()
        with pytest.raises(OutboundStoragePermissionError) as excinfo:
            resolve_document_link(
                source=AttachmentSource.GMAIL,
                reference="https://mail.google.com/mail/u/0/#inbox/abc123",
                credentials=None,
            )
        assert excinfo.value.context is not None
        assert excinfo.value.context["required_scope"] == "https://www.googleapis.com/auth/gmail.readonly"
        # Nothing reached storage — no manifest was written.
        assert tuple(store.iter_manifests()) == ()


def test_url_reference_refuses_and_writes_nothing(tmp_path: Path) -> None:
    """An arbitrary URL refuses with the scope error and stores nothing."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = AttachmentStore()
        with pytest.raises(OutboundStoragePermissionError) as excinfo:
            resolve_document_link(
                source=AttachmentSource.URL,
                reference="https://example.com/justificante.pdf",
                credentials=None,
            )
        assert excinfo.value.context is not None
        assert excinfo.value.context["required_scope"] == "https://www.googleapis.com/auth/drive.readonly"
        assert tuple(store.iter_manifests()) == ()
