"""Tests for encrypted SQL-backed attachment persistence."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.storage.attachment import AttachmentStore
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._enums import AttachmentKind, AttachmentSource
from .._errors import AttachmentNotFoundError, AttachmentValidationError
from .._models import Attachment

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="attachment-test") as profile:
        yield profile


def _attachment(body: bytes, *, tx_id: str = "tx-001", bucket_id: str = "bucket-a") -> Attachment:
    digest = hashlib.sha256(body).hexdigest()
    return Attachment(
        attachment_id=digest,
        kind=AttachmentKind.INVOICE_PDF,
        source=AttachmentSource.LOCAL_FILE,
        source_reference="invoice.pdf",
        sha256=digest,
        mime_type="application/pdf",
        bytes_size=len(body),
        captured_at=datetime(2026, 4, 27, 10, 0, tzinfo=UTC),
        linked_transaction_ids=(tx_id,),
        bucket_id=bucket_id,
        captured_by="operator-A",
        source_command="aeat app ledger attach",
        notes="deductible invoice",
    )


def test_blob_and_manifest_round_trip_without_plaintext_files(
    runtime_profile: TestRuntimeProfile,
) -> None:
    store = AttachmentStore()
    body = b"%PDF-1.4\nATTACHMENT_CANARY_00000000T\n%%EOF"
    digest = store.put_bytes(body)
    attachment = _attachment(body)
    store.write_manifest(attachment)

    assert digest == attachment.attachment_id
    assert store.read_bytes(digest) == body
    with store.open_bytes(digest) as handle:
        assert handle.read() == body
    loaded = store.load_manifest(digest)
    assert loaded == attachment
    assert loaded.captured_by == "operator-A"
    assert loaded.source_command == "aeat app ledger attach"
    assert loaded.bucket_id == "bucket-a"
    assert tuple(store.iter_manifests()) == (attachment,)
    store.verify_blob(digest)

    from ....tests.secure_sql import read_db_at_rest_bytes

    database_bytes = read_db_at_rest_bytes(runtime_profile.paths.db_dir / "aeat.db")
    assert b"secure_objects" in database_bytes
    assert body not in database_bytes
    assert b"ATTACHMENT_CANARY_00000000T" not in database_bytes
    assert digest.encode("utf-8") not in database_bytes
    assert b"deductible invoice" not in database_bytes


def test_un_enveloped_blob_is_refused(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """An un-enveloped blob payload must be refused, not silently returned.

    Every blob is wrapped with the envelope prefix at write time, so a stored
    payload without the prefix can only mean corruption. Writes raw content
    (no envelope prefix) directly through the secure-object substrate, then
    asserts :meth:`AttachmentStore.read_bytes` raises rather than returning the
    unframed bytes.
    """
    from datetime import UTC, datetime

    from ....adapters.persistence.storage.attachment import (
        _ATTACHMENT_BLOB_NAMESPACE,
        _ATTACHMENT_BLOB_SENSITIVITY,
        _ATTACHMENT_BLOB_VERSION,
    )

    store = AttachmentStore()
    body = b"%PDF-1.4\nun-enveloped blob\n%%EOF"
    digest = hashlib.sha256(body).hexdigest()
    store._objects_repo().save(
        namespace=_ATTACHMENT_BLOB_NAMESPACE,
        object_key=digest,
        classification=_ATTACHMENT_BLOB_SENSITIVITY,
        schema_version=_ATTACHMENT_BLOB_VERSION,
        written_at=datetime(2026, 4, 27, 10, 0, tzinfo=UTC),
        payload=body,
    )

    with pytest.raises(AttachmentValidationError, match=r"envelope prefix"):
        store.read_bytes(digest)


def test_put_file_reads_source_but_persists_only_secure_database_object(
    tmp_path: Path,
    runtime_profile: TestRuntimeProfile,
) -> None:
    source = tmp_path / "source.pdf"
    body = b"%PDF-1.4\nsource invoice\n%%EOF"
    source.write_bytes(body)
    store = AttachmentStore()

    digest, size = store.put_file(source)

    assert digest == hashlib.sha256(body).hexdigest()
    assert size == len(body)
    assert store.read_bytes(digest) == body
    assert not (runtime_profile.storage_root / "attachments").exists()


def test_missing_blob_and_invalid_digest_fail_closed() -> None:
    store = AttachmentStore()
    missing = "a" * 64

    with pytest.raises(AttachmentNotFoundError, match=r"attachment|not|found"):
        store.read_bytes(missing)
    with pytest.raises(AttachmentValidationError, match=r"sha256 must be a 64-character lowercase hex digest"):
        store.read_bytes("../escape")
