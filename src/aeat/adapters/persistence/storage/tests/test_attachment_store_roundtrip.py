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

Real active-profile runtime, real SQLite, no mocks.
A regression in the blob-namespace column encryption, the manifest
envelope schema, or the content-addressed digest pinning surfaces
as a strict ``bytes`` / pydantic inequality.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from ..sql._orm import SecureObjectRow

from .....core.config import override_settings
from .....core.errors import build_error_envelope, resolve_error_message
from .....core.external_constants import UTF_8_ENCODING
from .....domain.attachments._enums import AttachmentKind, AttachmentSource
from .....domain.attachments._errors import AttachmentPersistenceError, AttachmentValidationError
from .....domain.attachments._models import Attachment
from .....tests.secure_sql import isolated_runtime_profile
from ..attachment import _ATTACHMENT_MANIFEST_NAMESPACE, AttachmentStore
from ..crypto._encrypted_columns import (
    decrypt_secure_object_payload,
    encrypt_secure_object_payload,
    secure_object_payload_aad,
)
from ..sql.engine import get_engine

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _row_payload_aad(row: SecureObjectRow) -> bytes:
    """Reconstruct the row's payload AEAD associated data for corruption probes.

    The secure-object payload is encrypted with the row identity bound into the
    AEAD associated data, so a corruption test that rewrites the stored content
    must decrypt and re-encrypt under the same AAD (corrupting the *content* the
    manifest validator inspects, not producing invalid ciphertext).
    """
    return secure_object_payload_aad(row.namespace, bytes(row.object_key), row.schema_version)


def _decrypt_row_content(row: SecureObjectRow) -> bytes:
    return decrypt_secure_object_payload(bytes(row.payload), associated_data=_row_payload_aad(row))


def _encrypt_row_content(row: SecureObjectRow, content: bytes) -> bytes:
    return encrypt_secure_object_payload(content, associated_data=_row_payload_aad(row))


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

    with isolated_runtime_profile(tmp_path=tmp_path):
        store = AttachmentStore()
        payload = b"%PDF-1.4\n%attachment-store-roundtrip-canary\n" + b"\x00" * 64
        digest = store.put_bytes(payload)

        assert digest == hashlib.sha256(payload).hexdigest()
        assert store.read_bytes(digest) == payload
        store.verify_blob(digest)

        attachment = _make_attachment(sha256=digest, bytes_size=len(payload))
        store.write_manifest(attachment)
        loaded = store.load_manifest(attachment.attachment_id)
        listed = tuple(store.iter_manifests())

        assert loaded == attachment
        assert listed == (attachment,)
        assert loaded.linked_transaction_ids == ("tx-001", "tx-002")
        assert loaded.linked_invoice_ids == ("inv-2025-001",)
        assert loaded.metadata == {"vendor": "ACME SL", "currency": "EUR"}
        assert loaded.captured_by == "cli/aeat"
        assert loaded.bytes_size == len(payload)


def test_attachment_store_logical_paths_use_namespace_registry() -> None:
    store = AttachmentStore()
    digest = "a" * 64

    assert store.manifest_path(digest).as_posix() == f"db:/secure_objects/aeat.domain.attachments.manifests/{digest}"


def test_attachment_source_read_error_is_localized_without_path_leak(tmp_path: Path) -> None:
    store = AttachmentStore()
    missing = tmp_path / "private-client-alpha" / "invoice.pdf"

    with pytest.raises(AttachmentPersistenceError) as excinfo:
        store.put_file(missing)
    envelope = build_error_envelope(excinfo.value)
    with override_settings(aeat_output_language="en"):
        message = resolve_error_message(excinfo.value)

    assert excinfo.value.translated_message == "errors.fail.fail_financial_attachments_attachment_persistence"
    assert "private-client-alpha" not in str(excinfo.value)
    assert str(missing) not in str(excinfo.value)
    assert "private-client-alpha" not in message
    assert "private-client-alpha" not in str(envelope.context)
    assert envelope.context == {
        "operation": "read_source",
        "surface": "attachment_store",
    }


def test_attachment_manifest_id_sha_mismatch_surfaces_at_load(tmp_path: Path) -> None:
    """Anti-tautology proof: corrupting attachment_id vs sha256 must surface.

    :class:`Attachment` carries a model_validator enforcing
    ``attachment_id == sha256`` — the content-addressing guarantee
    the attachment store relies on. A persisted manifest whose
    sha256 is mutated post-save (without also rewriting
    attachment_id) must fail load via the model_validator.

    Persists a manifest, reaches into ``SecureObjectRow`` via
    ``session_scope``, surgically flips the sha256 field to a
    different digest while leaving attachment_id intact, and asserts
    the load path catches the drift.

    If this test passes silently with a corrupted sha256, the
    attachment store's content-addressing guarantee is tautological
    and the bytes-on-disk no longer prove the manifest's identity.
    """

    import json as _json

    from sqlalchemy import select

    from ..sql._orm import SecureObjectRow
    from ..sql.session import session_scope

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        engine = get_engine(profile.settings)
        store = AttachmentStore()
        payload = b"sample attachment body for anti-tautology proof"
        digest = store.put_bytes(payload)
        attachment = _make_attachment(sha256=digest, bytes_size=len(payload))
        store.write_manifest(attachment)

        with session_scope(engine) as session:
            stmt = select(SecureObjectRow).where(
                SecureObjectRow.namespace == _ATTACHMENT_MANIFEST_NAMESPACE,
                SecureObjectRow.object_key == attachment.attachment_id,
            )
            row = session.execute(stmt).scalar_one()
            envelope = _json.loads(_decrypt_row_content(row).decode(UTF_8_ENCODING))
            manifest = envelope["payload"]
            # write_manifest drops attachment_id from the persisted payload
            # (the row's object_key carries it as the content-addressing
            # key). The fixture invariant is that the persisted sha256
            # equals the in-memory attachment's attachment_id, which by
            # construction equals the digest of the bytes (line 124).
            assert manifest["sha256"] == attachment.attachment_id, (
                "fixture must persist matching sha256 + attachment_id for this proof test to be meaningful"
            )
            tampered_digest = hashlib.sha256(b"tampered body").hexdigest()
            manifest["sha256"] = tampered_digest
            row.payload = _encrypt_row_content(row, _json.dumps(envelope).encode(UTF_8_ENCODING))

        with pytest.raises(AttachmentValidationError, match="invalid attachment manifest"):
            store.load_manifest(attachment.attachment_id)


@pytest.mark.parametrize(
    ("field_name", "tampered_value", "expected_violation"),
    (
        ("classification", "operational", "manifest_classification"),
        ("schema_version", 99, "manifest_schema_version"),
    ),
)
def test_attachment_manifest_envelope_metadata_drift_fails_closed(
    tmp_path: Path,
    field_name: str,
    tampered_value: object,
    expected_violation: str,
) -> None:
    """Row metadata and embedded manifest-envelope metadata must agree."""

    import json as _json

    from sqlalchemy import select

    from ..sql._orm import SecureObjectRow
    from ..sql.session import session_scope

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        engine = get_engine(profile.settings)
        store = AttachmentStore()
        payload = b"attachment manifest envelope metadata proof"
        digest = store.put_bytes(payload)
        attachment = _make_attachment(sha256=digest, bytes_size=len(payload))
        store.write_manifest(attachment)

        with session_scope(engine) as session:
            stmt = select(SecureObjectRow).where(
                SecureObjectRow.namespace == _ATTACHMENT_MANIFEST_NAMESPACE,
                SecureObjectRow.object_key == attachment.attachment_id,
            )
            row = session.execute(stmt).scalar_one()
            envelope = _json.loads(_decrypt_row_content(row).decode(UTF_8_ENCODING))
            envelope[field_name] = tampered_value
            row.payload = _encrypt_row_content(row, _json.dumps(envelope).encode(UTF_8_ENCODING))

        with pytest.raises(AttachmentValidationError) as excinfo:
            store.load_manifest(attachment.attachment_id)

    assert excinfo.value.translated_message == "errors.integrity.integrity_financial_attachments_attachment_validation"
    assert excinfo.value.context == {
        "surface": "attachment_store",
        "violation": expected_violation,
    }


@pytest.mark.parametrize(
    "stored_payload",
    (
        bytes((0xFF,)),
        b"[]",
        b'{"payload": null}',
    ),
)
def test_malformed_attachment_manifest_payload_is_localized_for_all_read_paths(
    tmp_path: Path,
    stored_payload: bytes,
) -> None:
    """Malformed persisted manifest bytes must not escape as raw parser exceptions."""

    from sqlalchemy import select

    from ..sql._orm import SecureObjectRow
    from ..sql.session import session_scope

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        engine = get_engine(profile.settings)
        store = AttachmentStore()
        payload = b"attachment malformed manifest payload proof"
        digest = store.put_bytes(payload)
        attachment = _make_attachment(sha256=digest, bytes_size=len(payload))
        store.write_manifest(attachment)

        with session_scope(engine) as session:
            stmt = select(SecureObjectRow).where(
                SecureObjectRow.namespace == _ATTACHMENT_MANIFEST_NAMESPACE,
                SecureObjectRow.object_key == attachment.attachment_id,
            )
            row = session.execute(stmt).scalar_one()
            row.payload = _encrypt_row_content(row, stored_payload)

        for read_manifests in (
            lambda: store.load_manifest(attachment.attachment_id),
            lambda: list(store.iter_manifests()),
        ):
            with pytest.raises(AttachmentValidationError) as excinfo:
                read_manifests()
            assert excinfo.value.translated_message == (
                "errors.integrity.integrity_financial_attachments_attachment_validation"
            )
            assert excinfo.value.context == {
                "surface": "attachment_store",
                "violation": "manifest_payload",
            }
