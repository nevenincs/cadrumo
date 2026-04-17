"""End-to-end integration tests for the attachment service.

These tests touch the real filesystem with realistic scenarios beyond the
unit-level fixtures in ``test_store.py``. They are marked ``unit`` for
`pytest` collection (no external services are involved — the service is
local-disk-only), but they exercise the full CLI → service → store →
manifest pipeline with empty files, corrupted manifests, tampered blobs,
path-traversal attempts, and concurrent writers to prove the invariants
documented in the ADR and the rolling audit doc.

No mocks, patches, stubs, fakes, or skips are used — every test writes
and reads real bytes on a real ``tmp_path``.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...cli import app as root_app
from . import (
    AttachmentKind,
    AttachmentNotFoundError,
    AttachmentPersistenceError,
    AttachmentSource,
    AttachmentStore,
    AttachmentValidationError,
    add_attachment,
    list_attachments,
)

_RUNNER = CliRunner()
_MANIFEST_SUFFIX = ".json"


def _write_source(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def _add(
    store: AttachmentStore,
    source: Path,
    *,
    link_transaction_ids: tuple[str, ...] = (),
    link_invoice_ids: tuple[str, ...] = (),
    kind: AttachmentKind = AttachmentKind.RECEIPT_IMAGE,
) -> str:
    attachment = add_attachment(
        store,
        path=source,
        kind=kind,
        source=AttachmentSource.LOCAL_FILE,
        source_reference=str(source),
        mime_type="application/pdf",
        captured_at=datetime(2026, 4, 17, tzinfo=UTC),
        link_transaction_ids=link_transaction_ids,
        link_invoice_ids=link_invoice_ids,
    )
    return attachment.attachment_id


@pytest.mark.unit
def test_empty_file_ingest_produces_zero_byte_attachment(tmp_path: Path) -> None:
    """A zero-byte source must still produce a valid attachment manifest."""
    store = AttachmentStore.at(tmp_path)
    source = _write_source(tmp_path / "empty.bin", b"")

    digest, size = store.put_file(source)

    assert size == 0
    assert digest == hashlib.sha256(b"").hexdigest()
    assert store.read_bytes(digest) == b""
    with store.open_bytes(digest) as handle:
        assert handle.read() == b""


@pytest.mark.unit
def test_verify_blob_detects_tampered_bytes(tmp_path: Path) -> None:
    """A blob modified on disk must fail verification."""
    store = AttachmentStore.at(tmp_path)
    source = _write_source(tmp_path / "invoice.pdf", b"original-bytes")
    digest = _add(store, source)

    blob = store.blob_path(digest)
    blob.write_bytes(b"tampered-bytes-tampered-bytes")

    with pytest.raises(AttachmentValidationError):
        store.verify_blob(digest)


@pytest.mark.unit
def test_verify_blob_passes_for_untouched_bytes(tmp_path: Path) -> None:
    """A healthy blob must verify without error."""
    store = AttachmentStore.at(tmp_path)
    source = _write_source(tmp_path / "invoice.pdf", b"original-bytes")
    digest = _add(store, source)

    store.verify_blob(digest)


@pytest.mark.unit
def test_verify_blob_rejects_non_hex_attachment_id(tmp_path: Path) -> None:
    """Non-hex attachment IDs must be rejected before touching the filesystem."""
    store = AttachmentStore.at(tmp_path)
    with pytest.raises(AttachmentValidationError):
        store.verify_blob("not-a-digest")


@pytest.mark.unit
def test_verify_blob_raises_not_found_for_missing_blob(tmp_path: Path) -> None:
    """Missing blob files must surface as AttachmentNotFoundError."""
    store = AttachmentStore.at(tmp_path)
    with pytest.raises(AttachmentNotFoundError):
        store.verify_blob("a" * 64)


@pytest.mark.unit
def test_load_manifest_surfaces_corrupt_json_as_validation_error(tmp_path: Path) -> None:
    """Corrupted JSON manifests must surface as AttachmentValidationError."""
    store = AttachmentStore.at(tmp_path)
    store.manifests_dir.mkdir(parents=True, exist_ok=True)
    bogus = store.manifests_dir / ("a" * 64 + _MANIFEST_SUFFIX)
    bogus.write_text("{not json", encoding="utf-8")

    with pytest.raises(AttachmentValidationError):
        store.load_manifest("a" * 64)


@pytest.mark.unit
def test_load_manifest_rejects_filename_payload_mismatch(tmp_path: Path) -> None:
    """A manifest whose filename digest disagrees with its stored attachment_id must raise."""
    store = AttachmentStore.at(tmp_path)
    source = _write_source(tmp_path / "real.pdf", b"real-bytes")
    real_digest = _add(store, source)

    # Copy the legitimate manifest under a different filename (same content).
    impostor_name = "b" * 64 + _MANIFEST_SUFFIX
    impostor = store.manifests_dir / impostor_name
    impostor.write_text(store.manifest_path(real_digest).read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(AttachmentValidationError):
        store.load_manifest("b" * 64)

    # iter_manifests must also surface the mismatch rather than silently yield it.
    with pytest.raises(AttachmentValidationError):
        list(store.iter_manifests())


@pytest.mark.unit
def test_iter_manifests_skips_non_digest_filenames(tmp_path: Path) -> None:
    """Files under manifests/ that are not 64-char hex digests must be ignored."""
    store = AttachmentStore.at(tmp_path)
    source = _write_source(tmp_path / "real.pdf", b"real-bytes")
    digest = _add(store, source)

    store.manifests_dir.mkdir(parents=True, exist_ok=True)
    (store.manifests_dir / "README.json").write_text("# notes", encoding="utf-8")
    (store.manifests_dir / "not-a-hex-digest.json").write_text("garbage", encoding="utf-8")

    results = list(store.iter_manifests())
    assert [attachment.attachment_id for attachment in results] == [digest]


@pytest.mark.unit
def test_path_traversal_attempt_on_load_manifest_is_rejected(tmp_path: Path) -> None:
    """Untrusted attachment_id inputs must not escape the store root."""
    store = AttachmentStore.at(tmp_path)
    with pytest.raises(AttachmentValidationError):
        store.load_manifest("../../etc/passwd")


@pytest.mark.unit
def test_path_traversal_attempt_on_read_bytes_is_rejected(tmp_path: Path) -> None:
    """Untrusted sha256 inputs must not escape the blobs directory."""
    store = AttachmentStore.at(tmp_path)
    with pytest.raises(AttachmentValidationError):
        store.read_bytes("../../etc/passwd")


@pytest.mark.unit
def test_uppercase_hex_digest_is_rejected_for_ntfs_case_safety(tmp_path: Path) -> None:
    """Uppercase hex digests must be rejected so NTFS case-insensitivity cannot alias blobs."""
    store = AttachmentStore.at(tmp_path)
    with pytest.raises(AttachmentValidationError):
        store.read_bytes("A" * 64)
    with pytest.raises(AttachmentValidationError):
        store.manifest_path("A" * 64)


@pytest.mark.unit
def test_concurrent_put_bytes_preserves_first_writer_blob(tmp_path: Path) -> None:
    """Two threads ingesting the same bytes must converge on one unchanged blob."""
    store = AttachmentStore.at(tmp_path)
    data = b"shared-bytes-payload-contested"
    expected = hashlib.sha256(data).hexdigest()

    results: list[str] = []

    def worker() -> None:
        results.append(store.put_bytes(data))

    first_thread = threading.Thread(target=worker)
    second_thread = threading.Thread(target=worker)
    first_thread.start()
    second_thread.start()
    first_thread.join()
    second_thread.join()

    assert results == [expected, expected]
    blob = store.blob_path(expected)
    assert blob.read_bytes() == data
    # Blob must survive both writers; tempfiles must have been cleaned up.
    stray = sorted(p.name for p in store.blobs_dir.iterdir() if p.name != expected)
    assert stray == []


@pytest.mark.unit
def test_concurrent_put_file_preserves_first_writer_blob(tmp_path: Path) -> None:
    """Streaming writers racing on the same source must converge on one blob."""
    store = AttachmentStore.at(tmp_path)
    source = _write_source(tmp_path / "contended.bin", b"streaming-contested")
    expected = hashlib.sha256(b"streaming-contested").hexdigest()

    results: list[tuple[str, int]] = []

    def worker() -> None:
        results.append(store.put_file(source))

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    digests = {digest for digest, _ in results}
    sizes = {size for _, size in results}
    assert digests == {expected}
    assert sizes == {len(b"streaming-contested")}
    stray = sorted(p.name for p in store.blobs_dir.iterdir() if p.name != expected)
    assert stray == []


@pytest.mark.unit
def test_end_to_end_cli_round_trip_with_utf8_source_path(tmp_path: Path) -> None:
    """The CLI must survive a UTF-8 source path and produce a verifiable blob."""
    store_root = tmp_path / "store"
    utf8_dir = tmp_path / "fäcturas-año-2026"
    utf8_dir.mkdir()
    source = _write_source(utf8_dir / "invoice-áéíóú.pdf", b"utf8-payload")

    add_result = _RUNNER.invoke(
        root_app,
        ["attachments", "add", str(source), "--link-tx", "tx-1"],
        env={"AEAT_ATTACHMENTS_DIR": str(store_root)},
    )
    assert add_result.exit_code == 0, add_result.output

    payload = json.loads(add_result.stdout)
    digest = hashlib.sha256(b"utf8-payload").hexdigest()
    assert payload["attachment_id"] == digest
    assert payload["source_reference"].endswith("invoice-áéíóú.pdf")

    list_result = _RUNNER.invoke(
        root_app,
        ["attachments", "list"],
        env={"AEAT_ATTACHMENTS_DIR": str(store_root)},
    )
    assert list_result.exit_code == 0
    assert digest in list_result.output

    store = AttachmentStore.at(store_root)
    store.verify_blob(digest)


@pytest.mark.unit
def test_list_attachments_linked_to_invoice_matches_invoice_links(tmp_path: Path) -> None:
    """linked_to must filter attachments whose invoice link contains the identifier."""
    store = AttachmentStore.at(tmp_path)
    source_a = _write_source(tmp_path / "a.pdf", b"invoice-a")
    source_b = _write_source(tmp_path / "b.pdf", b"invoice-b")
    digest_a = _add(store, source_a, link_invoice_ids=("inv-1",))
    digest_b = _add(store, source_b, link_invoice_ids=("inv-2",))

    inv1 = list_attachments(store, linked_to="inv-1")
    assert [attachment.attachment_id for attachment in inv1] == [digest_a]

    inv2 = list_attachments(store, linked_to="inv-2")
    assert [attachment.attachment_id for attachment in inv2] == [digest_b]


@pytest.mark.unit
def test_add_attachment_raises_persistence_error_on_unreadable_source(tmp_path: Path) -> None:
    """An unreadable source (missing file) must raise AttachmentPersistenceError."""
    store = AttachmentStore.at(tmp_path)
    missing = tmp_path / "never-existed.bin"
    with pytest.raises(AttachmentPersistenceError):
        add_attachment(
            store,
            path=missing,
            kind=AttachmentKind.OTHER,
            source=AttachmentSource.LOCAL_FILE,
            source_reference=str(missing),
            mime_type="application/octet-stream",
            captured_at=datetime(2026, 4, 17, tzinfo=UTC),
        )


@pytest.mark.unit
def test_cli_show_on_malformed_attachment_id_surfaces_typed_error(tmp_path: Path) -> None:
    """`aeat attachments show <non-hex>` must exit cleanly with the typed error."""
    store_root = tmp_path / "store"
    result = _RUNNER.invoke(
        root_app,
        ["attachments", "show", "not-a-digest"],
        env={"AEAT_ATTACHMENTS_DIR": str(store_root)},
    )
    assert result.exit_code == 2
    assert "64-character lowercase hex digest" in result.output


@pytest.mark.unit
def test_cli_add_rejects_blank_metadata_value(tmp_path: Path) -> None:
    """`--metadata key=` (empty value) must exit 2 and persist nothing."""
    store_root = tmp_path / "store"
    source = _write_source(tmp_path / "x.pdf", b"x-bytes")
    result = _RUNNER.invoke(
        root_app,
        ["attachments", "add", str(source), "--metadata", "k="],
        env={"AEAT_ATTACHMENTS_DIR": str(store_root)},
    )
    assert result.exit_code == 2
    assert "--metadata value must not be blank" in result.output
    assert not store_root.exists() or not any((store_root / "manifests").glob("*.json"))
