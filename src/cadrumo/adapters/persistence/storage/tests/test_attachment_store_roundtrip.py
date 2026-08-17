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
from typing import Any

import pytest
from sqlalchemy import select

from .....core.config import override_settings
from .....core.errors import build_error_envelope, resolve_error_message
from .....core.secure_object_write import SecureObjectWrite
from .....domain.attachments import (
    Attachment,
    AttachmentKind,
    AttachmentPersistenceError,
    AttachmentSource,
    AttachmentValidationError,
)
from .....tests.attribute_scope import scoped_attribute
from .....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ..attachment import (
    _ATTACHMENT_BLOB_NAMESPACE,
    _ATTACHMENT_BLOB_SENSITIVITY,
    _ATTACHMENT_BLOB_VERSION,
    _ATTACHMENT_MANIFEST_NAMESPACE,
    AttachmentStore,
    resolve_attachment_store,
)
from ..crypto import (
    decrypt_secure_object_payload,
    encrypt_secure_object_payload,
    secure_object_payload_aad,
)
from ..sql import SecureObjectRow
from ..sql.engine import get_engine
from ..sql.session import session_scope

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


_CAPTURED_AT = datetime(2026, 5, 25, 13, 45, 0, tzinfo=UTC)
# The store refuses a manifest from another profile bucket, so the fixture
# names the same bucket the runtime profile provisions.
_BUCKET_ID = "3a1f0b2c-4d5e-4f60-8a71-92b3c4d5e6f7"
_EnvelopeMetadataDriftCase = tuple[str, str, object, str]
_MalformedManifestPayloadCase = tuple[str, bytes]

_ENVELOPE_METADATA_DRIFT_CASES: tuple[_EnvelopeMetadataDriftCase, ...] = (
    (
        "classification-operational-manifest_classification",
        "classification",
        "operational",
        "manifest_classification",
    ),
    ("schema_version-99-manifest_schema_version", "schema_version", 99, "manifest_schema_version"),
)

_MALFORMED_MANIFEST_PAYLOAD_CASES: tuple[_MalformedManifestPayloadCase, ...] = (
    ("invalid-utf8", bytes((0xFF,))),
    ("array-json", b"[]"),
    ("null-payload-json", b'{"payload": null}'),
)


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


def _manifest_row_statement(attachment_id: str) -> Any:
    return select(SecureObjectRow).where(
        SecureObjectRow.namespace == _ATTACHMENT_MANIFEST_NAMESPACE,
        SecureObjectRow.object_key == attachment_id,
    )


def _replace_manifest_row_payload(engine: Any, attachment_id: str, payload: bytes) -> None:
    with session_scope(engine) as session:
        row = session.execute(_manifest_row_statement(attachment_id)).scalar_one()
        row.payload = _encrypt_row_content(row, payload)


def _make_attachment(*, sha256: str, bytes_size: int) -> Attachment:
    """Build a fully-populated Attachment manifest.

    Two non-empty link tuples and a non-empty metadata mapping
    exercise the iterable-typed fields. A non-default ``notes``
    string and an optional ``captured_by`` value cover the rest of
    the surface.
    """

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
        linked_invoice_ids=("inv-2025-001",),
        bucket_id=_BUCKET_ID,
        captured_by="cli/aeat",
        source_command="aeat app attachments ingest",
        metadata={"vendor": "ACME SL", "currency": "EUR"},
        notes="Test attachment for roundtrip coverage.",
    )


def test_attachment_blob_and_manifest_round_trip(tmp_path: Path) -> None:
    """Bytes survive put_bytes -> read_bytes; manifest survives write -> load."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
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

    assert store.manifest_path(digest).as_posix() == f"db:/secure_objects/cadrumo.domain.attachments.manifests/{digest}"


def test_attachment_source_read_error_is_localized_without_path_leak(tmp_path: Path) -> None:
    store = AttachmentStore()
    missing = tmp_path / "private-client-alpha" / "invoice.pdf"

    with pytest.raises(AttachmentPersistenceError) as excinfo:
        store.put_file(missing)
    envelope = build_error_envelope(excinfo.value)
    with override_settings(cadrumo_output_language="en"):
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


def test_attachment_store_put_file_deduplicates_by_digest(tmp_path: Path) -> None:
    """A second ``put_file`` of identical content must not re-save the blob object.

    ``put_file`` delegates to ``put_bytes``, which short-circuits with
    ``objects.exists(...)`` before calling ``save`` a second time for a
    digest already on disk. Each ``save`` call mints a new
    ``SecureObjectRecord.revision_id`` (an upsert bumps the revision chain),
    so the revision id observed after the first write is a real, checkable
    proxy for "did a second underlying write happen". If ``put_file``
    regresses to unconditionally calling ``save`` (as it did before this
    delegation), the second call mints a fresh revision id and this
    assertion fails.
    """

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_file = source_dir / "invoice.pdf"
    source_file.write_bytes(b"%PDF-1.4\n%put-file-dedup-canary\n" + b"\x00" * 128)

    profile_dir = tmp_path / "profile"

    with isolated_runtime_profile(tmp_path=profile_dir, bucket_id=_BUCKET_ID):
        store = AttachmentStore()

        first_digest, first_size = store.put_file(source_file)
        first_record = store._objects_repo().load(
            _ATTACHMENT_BLOB_NAMESPACE,
            first_digest,
            expected_class=_ATTACHMENT_BLOB_SENSITIVITY,
            max_supported_version=_ATTACHMENT_BLOB_VERSION,
        )
        assert first_record is not None

        second_digest, second_size = store.put_file(source_file)
        second_record = store._objects_repo().load(
            _ATTACHMENT_BLOB_NAMESPACE,
            second_digest,
            expected_class=_ATTACHMENT_BLOB_SENSITIVITY,
            max_supported_version=_ATTACHMENT_BLOB_VERSION,
        )
        assert second_record is not None

        assert second_digest == first_digest
        assert second_size == first_size == source_file.stat().st_size
        assert second_record.revision_id == first_record.revision_id, (
            "second put_file of identical content re-saved the blob object instead of deduplicating"
        )


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

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        engine = get_engine(profile.settings)
        store = AttachmentStore()
        payload = b"sample attachment body for anti-tautology proof"
        digest = store.put_bytes(payload)
        attachment = _make_attachment(sha256=digest, bytes_size=len(payload))
        store.write_manifest(attachment)

        def tamper_sha256(envelope: dict[str, Any]) -> None:
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

        mutate_encrypted_secure_object_json(
            engine,
            row_statement=_manifest_row_statement(attachment.attachment_id),
            mutate=tamper_sha256,
        )

        with pytest.raises(AttachmentValidationError, match="invalid attachment manifest"):
            store.load_manifest(attachment.attachment_id)


def test_attachment_manifest_envelope_metadata_drift_fails_closed(
    tmp_path: Path,
) -> None:
    """Row metadata and embedded manifest-envelope metadata must agree."""

    for case_label, field_name, tampered_value, expected_violation in _ENVELOPE_METADATA_DRIFT_CASES:
        case_tmp_path = tmp_path / case_label
        case_tmp_path.mkdir()
        with isolated_runtime_profile(tmp_path=case_tmp_path, bucket_id=_BUCKET_ID) as profile:
            engine = get_engine(profile.settings)
            store = AttachmentStore()
            payload = b"attachment manifest envelope metadata proof"
            digest = store.put_bytes(payload)
            attachment = _make_attachment(sha256=digest, bytes_size=len(payload))
            store.write_manifest(attachment)

            def mutate_envelope(
                envelope: dict[str, Any],
                *,
                field: str = field_name,
                value: object = tampered_value,
            ) -> None:
                envelope[field] = value

            mutate_encrypted_secure_object_json(
                engine,
                row_statement=_manifest_row_statement(attachment.attachment_id),
                mutate=mutate_envelope,
            )

            with pytest.raises(AttachmentValidationError) as excinfo:
                store.load_manifest(attachment.attachment_id)

        assert (
            excinfo.value.translated_message == "errors.integrity.integrity_financial_attachments_attachment_validation"
        ), case_label
        assert excinfo.value.context == {
            "surface": "attachment_store",
            "violation": expected_violation,
        }, case_label


def test_malformed_attachment_manifest_payload_is_localized_for_all_read_paths(
    tmp_path: Path,
) -> None:
    """Malformed persisted manifest bytes must not escape as raw parser exceptions."""

    for case_label, stored_payload in _MALFORMED_MANIFEST_PAYLOAD_CASES:
        case_tmp_path = tmp_path / case_label
        case_tmp_path.mkdir()
        with isolated_runtime_profile(tmp_path=case_tmp_path, bucket_id=_BUCKET_ID) as profile:
            engine = get_engine(profile.settings)
            store = AttachmentStore()
            payload = b"attachment malformed manifest payload proof"
            digest = store.put_bytes(payload)
            attachment = _make_attachment(sha256=digest, bytes_size=len(payload))
            store.write_manifest(attachment)

            _replace_manifest_row_payload(engine, attachment.attachment_id, stored_payload)

            for read_path in ("load_manifest", "iter_manifests"):
                with pytest.raises(AttachmentValidationError) as excinfo:
                    if read_path == "load_manifest":
                        store.load_manifest(attachment.attachment_id)
                    else:
                        list(store.iter_manifests())
                assert excinfo.value.translated_message == (
                    "errors.integrity.integrity_financial_attachments_attachment_validation"
                ), f"{case_label}:{read_path}"
                assert excinfo.value.context == {
                    "surface": "attachment_store",
                    "violation": "manifest_payload",
                }, f"{case_label}:{read_path}"


def test_put_many_bytes_roundtrips_every_payload_in_order(tmp_path: Path) -> None:
    """The batched write must return the same bytes the per-record path would.

    Batching changes only the transaction granularity, so every payload must
    survive the encrypted boundary byte-for-byte and each returned digest must
    positionally match its input.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = AttachmentStore()
        payloads = [b"%PDF-1.4\ninvoice-" + str(index).encode() + b"\x00\xff" for index in range(6)]

        digests = store.put_many_bytes(payloads)

        assert len(digests) == len(payloads)
        for digest, payload in zip(digests, payloads, strict=True):
            assert digest == hashlib.sha256(payload).hexdigest()
            assert store.read_bytes(digest) == payload


def test_put_many_bytes_collapses_a_repeated_payload_within_one_batch(tmp_path: Path) -> None:
    """A digest repeated inside one batch is written once, not twice.

    A bulk import legitimately repeats a document — the same receipt attached
    to two rows. The namespace is content-addressed, so an identical digest
    means identical bytes and the second copy is redundant. Asserted through
    the store's own read path rather than a row count so the test binds to the
    contract callers see.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = AttachmentStore()
        repeated = b"%PDF-1.4\nthe-same-receipt"
        distinct = b"%PDF-1.4\na-different-document"

        digests = store.put_many_bytes([repeated, distinct, repeated])

        assert digests[0] == digests[2], "the repeated payload must resolve to one digest"
        assert digests[0] != digests[1]
        assert store.read_bytes(digests[0]) == repeated
        assert store.read_bytes(digests[1]) == distinct


def test_put_many_bytes_writes_a_repeated_payload_only_once(tmp_path: Path) -> None:
    """The in-batch dedup must actually skip the redundant write.

    Asserted by COUNTING the writes handed to ``save_many``, because the state
    it produces is identical either way: the upsert is idempotent, so a
    duplicated digest yields the same rows and the same readable bytes. A
    behavioural assertion therefore cannot see this at all — the first version
    of this proof asserted digests and bytes, and passed unchanged with the
    dedup disabled.

    What the dedup buys is real but invisible to state: encrypting and writing
    a 40 KB payload a second time for a document the batch already carries.
    The counter delegates to the real ``save_many``, so the write genuinely
    happens and this observes its shape.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        # The repository must be INJECTED: an AttachmentStore built without one
        # resolves a fresh repository per call, so a counter attached to any
        # single instance would never be the object the store actually writes
        # through -- the first version of this test patched exactly that and
        # silently observed nothing.
        objects = profile.repository
        store = AttachmentStore(objects=objects)
        repeated = b"%PDF-1.4 the-same-receipt"
        distinct = b"%PDF-1.4 a-different-document"
        real_save_many = objects.save_many
        seen: list[int] = []

        def counting_save_many(writes: tuple[SecureObjectWrite, ...]) -> None:
            seen.append(len(writes))
            real_save_many(writes)

        with scoped_attribute(objects, "save_many", counting_save_many):
            store.put_many_bytes([repeated, distinct, repeated])

        assert seen == [2], f"three payloads carrying two distinct digests must produce two writes, saw {seen}"


def test_put_many_bytes_reuses_payloads_already_stored(tmp_path: Path) -> None:
    """Re-ingesting a stored document is a no-op that still returns its digest.

    The second dedup axis: a batch overlapping an earlier import must neither
    fail nor rewrite, and must still answer with the digest so the caller can
    link to the existing blob.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = AttachmentStore()
        already = b"%PDF-1.4\nimported-last-week"
        first = store.put_bytes(already)

        digests = store.put_many_bytes([already, b"%PDF-1.4\nnew-this-run"])

        assert digests[0] == first
        assert store.read_bytes(digests[0]) == already
        assert store.read_bytes(digests[1]) == b"%PDF-1.4\nnew-this-run"


def test_put_many_bytes_on_an_empty_batch_writes_nothing(tmp_path: Path) -> None:
    """An empty ingest must not open a transaction or raise."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        assert AttachmentStore().put_many_bytes([]) == ()


def test_the_resolver_hands_back_the_injected_port_untouched(tmp_path: Path) -> None:
    """An injected store must be used as given, never wrapped or replaced.

    Every service accepting an optional custody port for testability relies on
    this identity: a resolver that re-constructed the default would silently
    write a test's bytes into the ambient store instead of the injected one.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        injected = AttachmentStore()

        assert resolve_attachment_store(injected) is injected


def test_the_resolver_constructs_the_encrypted_default_when_nothing_is_injected(tmp_path: Path) -> None:
    """Omitting the port yields the concrete encrypted store, not a stand-in.

    This is the single construction site the consuming packages delegate to, so
    the assertion that matters is that what comes back genuinely writes to
    encrypted custody rather than merely satisfying the protocol.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        resolved = resolve_attachment_store(None)

        assert isinstance(resolved, AttachmentStore)
        payload = b"%PDF-1.4\nresolved-default-store"
        digest = resolved.put_bytes(payload)
        assert AttachmentStore().read_bytes(digest) == payload
