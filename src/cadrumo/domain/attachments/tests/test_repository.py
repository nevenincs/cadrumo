"""Tests for encrypted SQL-backed attachment persistence."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.storage.attachment import AttachmentStore
from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ....core.storage_taxonomy import StorageCategory
from ....core.storage_taxonomy_locations import storage_path
from ....tests.secure_sql import TestRuntimeProfile
from ..enums import AttachmentKind, AttachmentSource
from ..errors import AttachmentNotFoundError, AttachmentValidationError
from ..models import Attachment

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET_ID = "8b159522-c2d5-490f-95f8-f1e936f45f7d"

runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=True, name="runtime_profile")


def _attachment(body: bytes, *, tx_id: str = "tx-001", bucket_id: str | None = _BUCKET_ID) -> Attachment:
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
    assert loaded.bucket_id == _BUCKET_ID
    assert tuple(store.iter_manifests()) == (attachment,)
    store.verify_blob(digest)

    from ....tests.secure_sql import read_db_at_rest_bytes

    database_bytes = read_db_at_rest_bytes(runtime_profile.paths.database_file)
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
    assert not storage_path(StorageCategory.ATTACHMENTS).exists()


def test_missing_blob_and_invalid_digest_fail_closed() -> None:
    store = AttachmentStore()
    missing = "a" * 64

    with pytest.raises(AttachmentNotFoundError, match=r"attachment|not|found"):
        store.read_bytes(missing)
    with pytest.raises(AttachmentValidationError, match=r"sha256 must be a 64-character lowercase hex digest"):
        store.read_bytes("../escape")


_FOREIGN_BUCKET_ID = "f0f0f0f0-1111-4111-8111-aaaaaaaaaaaa"


def test_foreign_bucket_manifest_is_refused_at_write(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Evidence belonging to another taxpayer must not enter this bucket's store."""
    del runtime_profile
    store = AttachmentStore()
    body = b"%PDF-1.4\nforeign bucket evidence\n%%EOF"
    store.put_bytes(body)

    with pytest.raises(AttachmentValidationError, match="another profile bucket"):
        store.write_manifest(_attachment(body, bucket_id=_FOREIGN_BUCKET_ID))


def test_foreign_bucket_manifest_is_isolated_from_load_and_listing(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Anti-tautology proof: isolation is durable, not a caller convention.

    Writes the foreign-bucket manifest straight through the secure-object
    substrate, bypassing the store's write guard, then asserts neither the
    single-item read nor the listing path returns it as local evidence.
    """
    del runtime_profile
    from datetime import UTC, datetime

    from ....adapters.persistence.storage.attachment import (
        _ATTACHMENT_MANIFEST_NAMESPACE,
        _ATTACHMENT_MANIFEST_SENSITIVITY,
        _ATTACHMENT_MANIFEST_VERSION,
    )
    from ....adapters.persistence.storage.envelope._envelope import Envelope

    store = AttachmentStore()
    body = b"%PDF-1.4\nforeign bucket evidence to isolate\n%%EOF"
    digest = store.put_bytes(body)
    foreign = _attachment(body, bucket_id=_FOREIGN_BUCKET_ID)
    envelope = Envelope[Attachment](
        schema_version=_ATTACHMENT_MANIFEST_VERSION,
        written_at=datetime(2026, 4, 27, 10, 0, tzinfo=UTC),
        classification=_ATTACHMENT_MANIFEST_SENSITIVITY,
        payload=foreign,
    )
    envelope_dict = json.loads(envelope.model_dump_json())
    del envelope_dict["payload"]["attachment_id"]
    store._objects_repo().save(
        namespace=_ATTACHMENT_MANIFEST_NAMESPACE,
        object_key=digest,
        classification=_ATTACHMENT_MANIFEST_SENSITIVITY,
        schema_version=_ATTACHMENT_MANIFEST_VERSION,
        written_at=envelope.written_at,
        payload=json.dumps(envelope_dict).encode("utf-8"),
    )

    with pytest.raises(AttachmentValidationError, match="another profile bucket"):
        store.load_manifest(digest)
    with pytest.raises(AttachmentValidationError, match="another profile bucket"):
        list(store.iter_manifests())


def test_manifest_without_a_declared_bucket_is_stamped_with_the_store_bucket(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """An unstamped manifest becomes self-describing rather than unattributable.

    The bucket is not part of the content address, so recording the store's own
    bucket at write time costs nothing and leaves no persisted evidence row
    whose ownership cannot be answered at read time.
    """
    del runtime_profile
    store = AttachmentStore()
    body = b"%PDF-1.4\nunstamped evidence\n%%EOF"
    digest = store.put_bytes(body)

    store.write_manifest(_attachment(body, bucket_id=None))

    assert store.load_manifest(digest).bucket_id == _BUCKET_ID


def test_same_bucket_manifest_round_trips(runtime_profile: TestRuntimeProfile) -> None:
    """Valid parity: a manifest naming this bucket loads and lists normally."""
    del runtime_profile
    store = AttachmentStore()
    body = b"%PDF-1.4\nlocal evidence\n%%EOF"
    digest = store.put_bytes(body)
    local = _attachment(body)

    store.write_manifest(local)

    assert store.load_manifest(digest) == local
    assert tuple(store.iter_manifests()) == (local,)
