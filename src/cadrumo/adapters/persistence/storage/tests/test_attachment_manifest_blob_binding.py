"""The attachment manifest's declared size and digest must reproduce from the blob.

:class:`Attachment` enforces ``attachment_id == sha256`` internally, but that is
a self-consistency check on the manifest alone. Nothing bound the declared
:attr:`Attachment.bytes_size` to the payload :class:`AttachmentStore` actually
holds, so a caller could persist a manifest claiming any length -- or claiming
bytes the store never received -- and the read paths returned that claim as
evidence metadata.

Real active-profile runtime, real encrypted SQLite, no mocks. The tampering
probes rewrite the stored ciphertext under the row's own AEAD associated data so
the *content* the validator inspects is corrupted, not the ciphertext framing.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from .....domain.attachments.enums import AttachmentKind, AttachmentSource
from .....domain.attachments.errors import AttachmentValidationError
from .....domain.attachments.models import Attachment
from .....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ..attachment import _ATTACHMENT_MANIFEST_NAMESPACE, AttachmentStore
from ..sql import SecureObjectRow
from ..sql.engine import get_engine

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_CAPTURED_AT = datetime(2026, 5, 25, 13, 45, 0, tzinfo=UTC)
_BUCKET_ID = "3a1f0b2c-4d5e-4f60-8a71-92b3c4d5e6f7"
_PAYLOAD = b"%PDF-1.4\n%attachment-manifest-blob-binding-canary\n" + b"\x00" * 48


def _manifest(*, sha256: str, bytes_size: int) -> Attachment:
    """Build a fully-populated manifest with every defaultable field non-default."""
    return Attachment(
        attachment_id=sha256,
        kind=AttachmentKind.INVOICE_PDF,
        source=AttachmentSource.LOCAL_FILE,
        source_reference="/local/path/to/invoice.pdf",
        sha256=sha256,
        mime_type="application/pdf",
        bytes_size=bytes_size,
        captured_at=_CAPTURED_AT,
        linked_transaction_ids=("tx-001", "tx-002"),
        linked_invoice_ids=("inv-2026-001",),
        bucket_id=_BUCKET_ID,
        captured_by="cli/aeat",
        source_command="aeat app ledger attach",
        metadata={"vendor": "ACME SL", "currency": "EUR"},
        notes="Manifest bound to its stored bytes.",
    )


def test_manifest_declaring_a_foreign_bytes_size_is_refused_at_write(tmp_path: Path) -> None:
    """A manifest whose bytes_size contradicts the stored payload must not persist."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = AttachmentStore()
        digest = store.put_bytes(_PAYLOAD)

        overstated = _manifest(sha256=digest, bytes_size=len(_PAYLOAD) + 967)

        with pytest.raises(AttachmentValidationError) as excinfo:
            store.write_manifest(overstated)

        assert excinfo.value.context == {
            "surface": "attachment_store",
            "violation": "manifest_bytes_size",
        }


def test_manifest_for_bytes_the_store_never_received_is_refused(tmp_path: Path) -> None:
    """A manifest referencing an absent blob is not evidence and must fail closed."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = AttachmentStore()
        absent_digest = hashlib.sha256(b"bytes that were never stored").hexdigest()

        orphan = _manifest(sha256=absent_digest, bytes_size=29)

        with pytest.raises(AttachmentValidationError) as excinfo:
            store.write_manifest(orphan)

        assert excinfo.value.context == {
            "surface": "attachment_store",
            "violation": "manifest_blob_missing",
        }


def test_tampered_stored_bytes_size_is_refused_on_load(tmp_path: Path) -> None:
    """A size mutated in durable storage must be caught by the read path.

    Anti-tautology proof for the write-side gate: the manifest is written
    through the real guarded path, then the persisted ``bytes_size`` is mutated
    in the encrypted row. If ``load_manifest`` returned that value, the binding
    would only be a construction-time convention rather than a durable contract.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        engine = get_engine(profile.settings)
        store = AttachmentStore()
        digest = store.put_bytes(_PAYLOAD)
        attachment = _manifest(sha256=digest, bytes_size=len(_PAYLOAD))
        store.write_manifest(attachment)

        def tamper_size(envelope: dict[str, Any]) -> None:
            manifest = envelope["payload"]
            assert manifest["bytes_size"] == len(_PAYLOAD), (
                "fixture must persist the true payload length for this proof to be meaningful"
            )
            manifest["bytes_size"] = len(_PAYLOAD) + 1

        mutate_encrypted_secure_object_json(
            engine,
            row_statement=select(SecureObjectRow).where(
                SecureObjectRow.namespace == _ATTACHMENT_MANIFEST_NAMESPACE,
                SecureObjectRow.object_key == attachment.attachment_id,
            ),
            mutate=tamper_size,
        )

        with pytest.raises(AttachmentValidationError) as excinfo:
            store.load_manifest(attachment.attachment_id)

        assert excinfo.value.context == {
            "surface": "attachment_store",
            "violation": "manifest_bytes_size",
        }


def test_manifest_bound_to_its_bytes_round_trips_intact(tmp_path: Path) -> None:
    """The valid parity case: a truthful manifest survives write, load, and listing."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = AttachmentStore()
        digest = store.put_bytes(_PAYLOAD)
        attachment = _manifest(sha256=digest, bytes_size=len(_PAYLOAD))

        store.write_manifest(attachment)
        loaded = store.load_manifest(attachment.attachment_id)
        listed = tuple(store.iter_manifests())

        assert loaded == attachment
        assert listed == (attachment,)
        assert loaded.bytes_size == len(store.read_bytes(digest))
