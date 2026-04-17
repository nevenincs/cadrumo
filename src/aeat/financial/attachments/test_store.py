"""Unit tests for the attachment byte + manifest store."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aeat.financial.attachments import (
    Attachment,
    AttachmentKind,
    AttachmentNotFoundError,
    AttachmentSource,
    AttachmentStore,
    add_attachment,
    list_attachments,
    load_attachment,
)


def _write_source(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


def _add_default(
    store: AttachmentStore,
    source: Path,
    *,
    link_transaction_ids: tuple[str, ...] = (),
    link_invoice_ids: tuple[str, ...] = (),
    kind: AttachmentKind = AttachmentKind.RECEIPT_IMAGE,
) -> Attachment:
    return add_attachment(
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


@pytest.mark.unit
def test_put_bytes_is_deterministic_and_idempotent(tmp_path: Path) -> None:
    """Same bytes always hash to the same digest and reuse the existing blob."""
    store = AttachmentStore.at(tmp_path)
    data = b"receipt-bytes-payload"
    expected = hashlib.sha256(data).hexdigest()

    first_digest = store.put_bytes(data)
    blob_path = store.blob_path(first_digest)
    first_written_at = blob_path.stat().st_mtime_ns
    first_content = blob_path.read_bytes()

    second_digest = store.put_bytes(data)

    assert first_digest == expected
    assert second_digest == expected
    assert blob_path.read_bytes() == first_content == data
    assert blob_path.stat().st_mtime_ns == first_written_at


@pytest.mark.unit
def test_read_bytes_returns_raw_content(tmp_path: Path) -> None:
    """read_bytes must return the exact bytes previously stored."""
    store = AttachmentStore.at(tmp_path)
    data = b"raw-bytes"
    digest = store.put_bytes(data)
    assert store.read_bytes(digest) == data


@pytest.mark.unit
def test_read_bytes_raises_not_found_for_missing_blob(tmp_path: Path) -> None:
    """Reading an unknown digest must raise the typed not-found error."""
    store = AttachmentStore.at(tmp_path)
    with pytest.raises(AttachmentNotFoundError):
        store.read_bytes("a" * 64)


@pytest.mark.unit
def test_add_attachment_stores_bytes_and_manifest_separately(tmp_path: Path) -> None:
    """Bytes land in blobs/ and manifests land in manifests/."""
    store = AttachmentStore.at(tmp_path)
    source = _write_source(tmp_path / "source.pdf", b"pdf-bytes")

    attachment = _add_default(store, source)

    assert attachment.bytes_size == len(b"pdf-bytes")
    assert store.blob_path(attachment.sha256).exists()
    assert store.manifest_path(attachment.attachment_id).exists()
    assert store.blobs_dir == tmp_path.resolve() / "blobs"
    assert store.manifests_dir == tmp_path.resolve() / "manifests"
    assert attachment.attachment_id == attachment.sha256
    reloaded = load_attachment(store, attachment.attachment_id)
    assert reloaded == attachment


@pytest.mark.unit
def test_re_ingesting_same_bytes_merges_links_without_duplicating_blob(tmp_path: Path) -> None:
    """A second add with a new link must merge, not replace."""
    store = AttachmentStore.at(tmp_path)
    source = _write_source(tmp_path / "invoice.pdf", b"invoice-bytes")

    first = _add_default(store, source, link_transaction_ids=("tx-1",))
    second = _add_default(store, source, link_transaction_ids=("tx-2",), link_invoice_ids=("inv-1",))

    assert first.attachment_id == second.attachment_id
    assert second.linked_transaction_ids == ("tx-1", "tx-2")
    assert second.linked_invoice_ids == ("inv-1",)
    blob_files = sorted(store.blobs_dir.iterdir())
    manifest_files = sorted(store.manifests_dir.iterdir())
    assert len(blob_files) == 1
    assert len(manifest_files) == 1


@pytest.mark.unit
def test_list_attachments_filters_by_linked_transaction_or_invoice(tmp_path: Path) -> None:
    """list_attachments respects linked_to filtering across both link sets."""
    store = AttachmentStore.at(tmp_path)
    source_a = _write_source(tmp_path / "a.pdf", b"a-bytes")
    source_b = _write_source(tmp_path / "b.pdf", b"b-bytes")

    _add_default(store, source_a, link_transaction_ids=("tx-1",))
    _add_default(store, source_b, link_invoice_ids=("inv-9",))

    linked_to_tx1 = list_attachments(store, linked_to="tx-1")
    linked_to_inv9 = list_attachments(store, linked_to="inv-9")
    linked_to_missing = list_attachments(store, linked_to="nope")

    assert len(linked_to_tx1) == 1
    assert len(linked_to_inv9) == 1
    assert linked_to_missing == ()


@pytest.mark.unit
def test_list_attachments_filters_by_kind(tmp_path: Path) -> None:
    """list_attachments respects the kind filter independent of linkage."""
    store = AttachmentStore.at(tmp_path)
    source_a = _write_source(tmp_path / "a.pdf", b"a-bytes")
    source_b = _write_source(tmp_path / "b.pdf", b"b-bytes")

    _add_default(store, source_a, kind=AttachmentKind.INVOICE_PDF)
    _add_default(store, source_b, kind=AttachmentKind.RECEIPT_IMAGE)

    invoices = list_attachments(store, kind=AttachmentKind.INVOICE_PDF)
    assert tuple(item.kind for item in invoices) == (AttachmentKind.INVOICE_PDF,)


@pytest.mark.unit
def test_blob_without_manifest_is_not_surfaced_by_listing(tmp_path: Path) -> None:
    """Orphan bytes must not appear in iter_manifests / list_attachments output."""
    store = AttachmentStore.at(tmp_path)
    orphan_digest = store.put_bytes(b"orphan")
    assert store.blob_path(orphan_digest).exists()
    assert list_attachments(store) == ()


@pytest.mark.unit
def test_iter_manifests_is_sorted_by_filename(tmp_path: Path) -> None:
    """Iteration order is deterministic by sorted manifest filename."""
    store = AttachmentStore.at(tmp_path)
    payloads = [tmp_path / f"{name}.bin" for name in ("one", "two", "three")]
    for index, path in enumerate(payloads):
        path.write_bytes(f"payload-{index}".encode())
        _add_default(store, path)

    ids_iter = [attachment.attachment_id for attachment in store.iter_manifests()]
    ids_list = [attachment.attachment_id for attachment in list_attachments(store)]

    assert ids_iter == sorted(ids_iter)
    assert ids_list == sorted(ids_list)


@pytest.mark.unit
def test_add_attachment_raises_persistence_error_for_missing_source(tmp_path: Path) -> None:
    """Source-read failures are translated to AttachmentPersistenceError."""
    from aeat.financial.attachments import AttachmentPersistenceError

    store = AttachmentStore.at(tmp_path)
    missing = tmp_path / "does-not-exist.bin"
    with pytest.raises(AttachmentPersistenceError):
        _add_default(store, missing)


@pytest.mark.unit
def test_manifest_round_trips_to_and_from_disk(tmp_path: Path) -> None:
    """A stored manifest reloads into an equal Attachment."""
    store = AttachmentStore.at(tmp_path)
    source = _write_source(tmp_path / "round-trip.pdf", b"round-trip-bytes")

    attachment = _add_default(store, source, link_transaction_ids=("tx-1", "tx-2"))
    reloaded = store.load_manifest(attachment.attachment_id)

    assert reloaded == attachment
