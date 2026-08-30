"""Crash-injection test for the attachment blob/manifest put window.

The modern ``AttachmentStore`` writes the content-addressed blob and its
manifest as two separate rows in the SAME encrypted SQLite secure-object store
(``put_bytes`` / ``put_file`` then ``write_manifest`` - two distinct
``SecureObjectRepository.save`` calls). A crash between them leaves an orphan
blob row with no manifest row. The recovery contract is that the orphan is
inert: it is keyed by ``sha256(content)`` (content-addressed), unreferenced (no
manifest resolves it), and idempotent-dedup on retry (a re-``put`` reuses the
existing row). An orphan-blob GC sweep is a documented non-goal - an
unreferenced content-addressed blob is harmless and dedup-reused, never
duplicated.

Real active-profile runtime, real encrypted SQLite, no mocks. The crash is
simulated by writing the blob and stopping before the manifest write; the
anti-tautology proof writes the manifest afterwards and shows the orphan becomes
a resolvable attachment, so the "not found" assertion is caused by the missing
manifest, not a broken store.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....domain.attachments.enums import AttachmentKind, AttachmentSource
from .....domain.attachments.errors import AttachmentNotFoundError
from .....domain.attachments.models import Attachment
from .....tests.secure_sql import isolated_runtime_profile
from ..attachment import AttachmentStore

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BLOB = b"invoice pdf bytes for the attachment crash window"
_CAPTURED_AT = datetime(2026, 7, 2, 9, 30, 0, tzinfo=UTC)


def _manifest_for(sha256: str, *, bytes_size: int) -> Attachment:
    return Attachment(
        attachment_id=sha256,
        kind=AttachmentKind.INVOICE_PDF,
        source=AttachmentSource.LOCAL_FILE,
        source_reference="/local/path/to/invoice.pdf",
        sha256=sha256,
        mime_type="application/pdf",
        bytes_size=bytes_size,
        captured_at=_CAPTURED_AT,
        bucket_id="b" * 32,
    )


def test_orphan_blob_is_unreferenced_and_idempotently_reclaimed(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        store = AttachmentStore(objects=profile.repository)

        # --- Simulate the crash: write the blob (put), then stop BEFORE the
        # manifest write. Two separate secure-object saves; the interruption is
        # simply not calling the second one.
        digest = store.put_bytes(_BLOB)

        # The orphan blob is readable by its content digest ...
        assert store.read_bytes(digest) == _BLOB
        # ... but it is unreferenced: no manifest resolves it, so the operator-
        # facing lookup fails closed rather than returning a half-record.
        with pytest.raises(AttachmentNotFoundError):
            store.load_manifest(digest)
        # ... and it does not appear in the manifest inventory.
        assert all(manifest.attachment_id != digest for manifest in store.iter_manifests())

        # Recovery is idempotent: a re-put reuses the existing content-addressed
        # row (same digest), never duplicating the blob.
        redigest = store.put_bytes(_BLOB)
        assert redigest == digest
        assert store.read_bytes(digest) == _BLOB

        # --- Anti-tautology: completing the interrupted write (the manifest)
        # turns the orphan into a fully resolvable attachment, proving the
        # "not found" above was caused by the missing manifest, not a broken
        # blob store.
        store.write_manifest(_manifest_for(digest, bytes_size=len(_BLOB)))
        resolved = store.load_manifest(digest)
        assert resolved.attachment_id == digest
        assert resolved.sha256 == digest
        assert any(manifest.attachment_id == digest for manifest in store.iter_manifests())
