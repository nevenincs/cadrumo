"""Strict roundtrip across the encrypted Attachment boundary.

The :class:`AttachmentStore` adapter satisfies the domain-layer
:class:`AttachmentStoreProtocol` over :class:`SecureObjectRepository`.
Bytes flow through ``put_bytes`` (content-addressed) and manifests
flow through ``write_manifest`` / ``load_manifest``. This test
asserts that the full cycle preserves both surfaces:

* A blob written via ``put_bytes`` reads back byte-identical via
  ``read_bytes`` (the content-addressing invariant) and survives
  ``verify_blob`` re-hashing.
* A manifest written via ``write_manifest`` loads back via
  ``load_manifest`` with strict pydantic equality, including the
  optional fields and the tuple-typed link lists.

Real :class:`EphemeralMasterKeyProvider`, real SQLite, no mocks.
A regression in the blob-namespace column encryption, the manifest
envelope schema, or the content-addressed digest pinning surfaces
as a strict ``bytes`` / pydantic inequality.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core.config import Settings
from ....domain.attachments._enums import AttachmentKind, AttachmentSource
from ....domain.attachments._models import Attachment
from . import EphemeralMasterKeyProvider, override_master_key_provider
from .attachment import AttachmentStore
from .sql import SecureObjectRepository
from .sql._orm import Base
from .sql.engine import create_engine_from_settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _make_attachment(*, sha256: str, bytes_size: int) -> Attachment:
    """Build a fully-populated Attachment manifest.

    Two non-empty link tuples and a non-empty metadata mapping
    exercise the iterable-typed fields. A non-default ``notes``
    string and an optional ``captured_by`` value cover the rest of
    the surface.
    """

    now = datetime.now(UTC).replace(microsecond=0)
    return Attachment(
        attachment_id=sha256,
        kind=AttachmentKind.INVOICE_PDF,
        source=AttachmentSource.LOCAL_FILE,
        source_reference="/local/path/to/invoice.pdf",
        sha256=sha256,
        mime_type="application/pdf",
        bytes_size=bytes_size,
        captured_at=now,
        linked_transaction_ids=("tx-001", "tx-002"),
        linked_invoice_ids=("inv-2025-001",),
        bucket_id="b" * 32,
        captured_by="cli/aeat",
        source_command="aeat app attachments ingest",
        metadata={"vendor": "ACME SL", "currency": "EUR"},
        notes="Test attachment for roundtrip coverage.",
    )


def test_attachment_blob_and_manifest_round_trip(tmp_path: Path) -> None:
    """Bytes survive put_bytes -> read_bytes; manifest survives write -> load."""

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "attachment-roundtrip.db"
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        objects = SecureObjectRepository(engine=engine)
        store = AttachmentStore(objects=objects)

        # --- Blob round-trip ---------------------------------------------
        payload = b"%PDF-1.4\n%attachment-store-roundtrip-canary\n" + b"\x00" * 64
        digest = store.put_bytes(payload)

        # Content-addressing invariant: the returned digest is the
        # SHA-256 of the input bytes. A regression in the put path
        # would return a digest that did not match.
        assert digest == hashlib.sha256(payload).hexdigest()

        read_back = store.read_bytes(digest)
        assert read_back == payload

        # verify_blob re-hashes the stored bytes; a mangled column
        # would surface here as a digest mismatch raised by the
        # store, not as a silent corruption on read.
        store.verify_blob(digest)

        # --- Manifest round-trip -----------------------------------------
        attachment = _make_attachment(sha256=digest, bytes_size=len(payload))
        store.write_manifest(attachment)
        loaded = store.load_manifest(attachment.attachment_id)

        assert loaded == attachment
        # Per-field witnesses for the iterable / optional fields most
        # likely to silently drop in a regression.
        assert loaded.linked_transaction_ids == ("tx-001", "tx-002")
        assert loaded.linked_invoice_ids == ("inv-2025-001",)
        assert loaded.metadata == {"vendor": "ACME SL", "currency": "EUR"}
        assert loaded.captured_by == "cli/aeat"
        assert loaded.bytes_size == len(payload)
    finally:
        engine.dispose()
        override_master_key_provider(None)
