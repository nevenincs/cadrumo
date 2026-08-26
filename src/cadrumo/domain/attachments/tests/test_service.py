"""Tests for the attachment service helpers."""

from __future__ import annotations

import ast
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.storage.attachment import AttachmentStore
from ....tests.secure_sql import isolated_runtime_profile
from .. import _service as attachment_service
from .._enums import AttachmentKind, AttachmentSource
from .._models import Attachment
from .._service import (
    AttachmentBytesContent,
    AttachmentFileContent,
    AttachmentIngestionRequest,
    add_attachment,
    link_attachment_invoice,
    link_attachment_transaction,
    list_attachments,
    load_attachment,
)
from ..errors import AttachmentNotFoundError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CAPTURED_AT = datetime(2026, 6, 30, 9, 0, 0, tzinfo=UTC)
# The store refuses a manifest from another profile bucket, so the fixture
# names the same bucket the runtime profile provisions.
_SERVICE_BUCKET_ID = "5c2d1e0a-7b8c-4d9e-8f01-2a3b4c5d6e7f"


def _add_text_attachment(store: AttachmentStore, path: Path, *, source_reference: str) -> Attachment:
    return add_attachment(
        store,
        content=AttachmentFileContent(path=path),
        request=AttachmentIngestionRequest(
            kind=AttachmentKind.OTHER,
            source=AttachmentSource.LOCAL_FILE,
            source_reference=source_reference,
            mime_type="text/plain",
            captured_at=_CAPTURED_AT,
        ),
    )


def test_add_and_load_attachment_roundtrips_through_real_store(tmp_path: Path) -> None:
    """add_attachment persists; load_attachment reads back identical metadata."""

    payload = b"Hello world. This is the test attachment body."
    source_file = tmp_path / "doc.txt"
    source_file.write_bytes(payload)

    with isolated_runtime_profile(tmp_path=tmp_path):
        store = AttachmentStore()
        added = _add_text_attachment(store, source_file, source_reference="test-doc")
        assert added.attachment_id
        expected = hashlib.sha256(payload).hexdigest()
        assert added.attachment_id == expected

        loaded = load_attachment(store, added.attachment_id)
        assert loaded.attachment_id == added.attachment_id
        assert loaded.kind == AttachmentKind.OTHER
        assert loaded.source == AttachmentSource.LOCAL_FILE


def test_load_attachment_raises_on_unknown_id(tmp_path: Path) -> None:
    """load_attachment surfaces a typed not-found error for a missing id."""

    with isolated_runtime_profile(tmp_path=tmp_path):
        store = AttachmentStore()
        with pytest.raises(AttachmentNotFoundError):
            load_attachment(store, "deadbeef" * 8)


def test_list_attachments_returns_every_persisted_record(tmp_path: Path) -> None:
    """list_attachments enumerates every record the caller added."""

    with isolated_runtime_profile(tmp_path=tmp_path):
        store = AttachmentStore()
        first = tmp_path / "one.txt"
        first.write_bytes(b"first")
        second = tmp_path / "two.txt"
        second.write_bytes(b"second")

        a = _add_text_attachment(store, first, source_reference="first")
        b = _add_text_attachment(store, second, source_reference="second")
        rows = list_attachments(store)
        ids = {row.attachment_id for row in rows}
        assert a.attachment_id in ids
        assert b.attachment_id in ids


def test_link_attachment_invoice_appends_and_persists_through_real_store(tmp_path: Path) -> None:
    """The invoice id is genuinely persisted -- reload through a fresh manifest read."""

    source_file = tmp_path / "invoice.pdf"
    source_file.write_bytes(b"%PDF-1.4 real invoice bytes")

    with isolated_runtime_profile(tmp_path=tmp_path):
        store = AttachmentStore()
        added = _add_text_attachment(store, source_file, source_reference="invoice-evidence")
        assert added.linked_invoice_ids == ()

        updated = link_attachment_invoice(store, attachment_id=added.attachment_id, invoice_id="invoice-abc")

        assert updated.linked_invoice_ids == ("invoice-abc",)
        # Reload through a FRESH manifest read: the link is genuinely persisted,
        # not merely returned by this call.
        reloaded = load_attachment(store, added.attachment_id)
        assert reloaded.linked_invoice_ids == ("invoice-abc",)
        # Every other field is unchanged: only the link tuple was touched.
        assert reloaded.sha256 == added.sha256
        assert reloaded.mime_type == added.mime_type
        assert reloaded.source_reference == added.source_reference


def test_link_attachment_invoice_is_idempotent_on_repeat_link(tmp_path: Path) -> None:
    """Re-linking the same invoice id is a no-op, never a growing duplicate tuple."""

    source_file = tmp_path / "invoice.pdf"
    source_file.write_bytes(b"%PDF-1.4 repeat-link invoice bytes")

    with isolated_runtime_profile(tmp_path=tmp_path):
        store = AttachmentStore()
        added = _add_text_attachment(store, source_file, source_reference="repeat-link-evidence")

        first = link_attachment_invoice(store, attachment_id=added.attachment_id, invoice_id="invoice-xyz")
        second = link_attachment_invoice(store, attachment_id=added.attachment_id, invoice_id="invoice-xyz")

        assert first.linked_invoice_ids == ("invoice-xyz",)
        assert second.linked_invoice_ids == ("invoice-xyz",)
        reloaded = load_attachment(store, added.attachment_id)
        assert reloaded.linked_invoice_ids == ("invoice-xyz",)


def test_link_attachment_invoice_appends_a_second_distinct_invoice(tmp_path: Path) -> None:
    """Linking a second, different invoice id extends the tuple rather than replacing it."""

    source_file = tmp_path / "invoice.pdf"
    source_file.write_bytes(b"%PDF-1.4 multi-link invoice bytes")

    with isolated_runtime_profile(tmp_path=tmp_path):
        store = AttachmentStore()
        added = _add_text_attachment(store, source_file, source_reference="multi-link-evidence")

        link_attachment_invoice(store, attachment_id=added.attachment_id, invoice_id="invoice-one")
        second = link_attachment_invoice(store, attachment_id=added.attachment_id, invoice_id="invoice-two")

        assert second.linked_invoice_ids == ("invoice-one", "invoice-two")


def test_link_attachment_invoice_makes_the_invoice_discoverable_via_list_attachments(tmp_path: Path) -> None:
    """The attachment is discoverable from the invoice id via ``list_attachments(linked_to=...)``."""

    source_file = tmp_path / "invoice.pdf"
    source_file.write_bytes(b"%PDF-1.4 discoverable invoice bytes")

    with isolated_runtime_profile(tmp_path=tmp_path):
        store = AttachmentStore()
        added = _add_text_attachment(store, source_file, source_reference="discoverable-evidence")
        link_attachment_invoice(store, attachment_id=added.attachment_id, invoice_id="invoice-findme")

        found = list_attachments(store, linked_to="invoice-findme")

        assert len(found) == 1
        assert found[0].attachment_id == added.attachment_id


def test_link_attachment_invoice_raises_not_found_for_unknown_attachment(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        store = AttachmentStore()
        with pytest.raises(AttachmentNotFoundError):
            link_attachment_invoice(store, attachment_id="deadbeef" * 8, invoice_id="invoice-abc")


def test_link_attachment_transaction_appends_and_persists_through_real_store(tmp_path: Path) -> None:
    """The transaction link uses the same real manifest-update path as invoice links."""
    source_file = tmp_path / "transaction.pdf"
    source_file.write_bytes(b"%PDF-1.4 transaction evidence bytes")

    with isolated_runtime_profile(tmp_path=tmp_path):
        store = AttachmentStore()
        added = _add_text_attachment(store, source_file, source_reference="transaction-evidence")
        updated = link_attachment_transaction(
            store,
            attachment_id=added.attachment_id,
            transaction_id="transaction-abc",
        )
        reloaded = load_attachment(store, added.attachment_id)

    assert updated.linked_transaction_ids == ("transaction-abc",)
    assert reloaded.linked_transaction_ids == ("transaction-abc",)
    assert reloaded.linked_invoice_ids == ()


def test_attachment_service_has_one_typed_ingestion_and_relation_update_core() -> None:
    """The public surface cannot grow a second byte-ingestion or link-update body."""
    service_path = Path(attachment_service.__file__)
    assert not (service_path.parent / "_ids.py").exists()
    tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

    assert not {name for name in functions if name.startswith("add_attachment_")}
    assert {"add_attachment", "_store_content", "_persist_attachment", "_link_attachment"} <= functions.keys()

    def called_names(function: ast.FunctionDef) -> set[str]:
        return {
            node.func.id
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }

    assert {"_store_content", "_persist_attachment"} <= called_names(functions["add_attachment"])
    assert "_link_attachment" in called_names(functions["link_attachment_invoice"])
    assert "_link_attachment" in called_names(functions["link_attachment_transaction"])

    manifest_writers = {
        function.name
        for function in functions.values()
        if any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "write_manifest"
            for node in ast.walk(function)
        )
    }
    assert manifest_writers == {"_persist_attachment", "_link_attachment"}


def test_same_byte_reingestion_accumulates_links_and_keeps_the_first_capture(
    tmp_path: Path,
) -> None:
    """Two observations of identical bytes must not erase each other's evidence.

    The content digest is the manifest key, so a second ingestion of the same
    document lands on the same row. It is a second *observation* -- a different
    channel, a different time, a different transaction it evidences -- and the
    unconditional upsert dropped the first one's links and capture context.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SERVICE_BUCKET_ID):
        store = AttachmentStore()
        data = b"%PDF-1.4\nsame-byte evidence observed twice\n%%EOF"
        first_capture = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
        second_capture = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)

        first = add_attachment(
            store,
            content=AttachmentBytesContent(data=data),
            request=AttachmentIngestionRequest(
                kind=AttachmentKind.INVOICE_PDF,
                source=AttachmentSource.LOCAL_FILE,
                source_reference="source-A",
                mime_type="application/pdf",
                captured_at=first_capture,
                bucket_id=_SERVICE_BUCKET_ID,
                link_transaction_ids=("tx-A",),
                metadata={"channel": "A", "only-a": "kept"},
            ),
        )
        add_attachment(
            store,
            content=AttachmentBytesContent(data=data),
            request=AttachmentIngestionRequest(
                kind=AttachmentKind.INVOICE_PDF,
                source=AttachmentSource.GOOGLE_DRIVE,
                source_reference="source-B",
                mime_type="application/pdf",
                captured_at=second_capture,
                bucket_id=_SERVICE_BUCKET_ID,
                link_transaction_ids=("tx-B",),
                metadata={"channel": "B", "only-b": "added"},
            ),
        )

        merged = load_attachment(store, first.attachment_id)
        listed = list_attachments(store)

    assert merged.linked_transaction_ids == ("tx-A", "tx-B")
    assert merged.captured_at == first_capture
    assert merged.source_reference == "source-A"
    assert merged.source is AttachmentSource.LOCAL_FILE
    assert merged.metadata["only-a"] == "kept"
    assert merged.metadata["only-b"] == "added"
    # A key both observations set keeps the earlier value, so the merge does not
    # depend on which ingestion ran last.
    assert merged.metadata["channel"] == "A"
    assert len(listed) == 1


def test_same_byte_merge_is_independent_of_ingestion_order(tmp_path: Path) -> None:
    """Reversing the ingestion order must not change what the links contain.

    The accumulating facts are a set, so the union is order-independent even
    though the first-seen ordering of the tuple differs.
    """
    data = b"%PDF-1.4\norder-independent same-byte evidence\n%%EOF"

    def _ingest(order: tuple[str, str], root: Path) -> tuple[str, ...]:
        with isolated_runtime_profile(tmp_path=root, bucket_id=_SERVICE_BUCKET_ID):
            store = AttachmentStore()
            attachment_id = ""
            for index, transaction_id in enumerate(order):
                attachment = add_attachment(
                    store,
                    content=AttachmentBytesContent(data=data),
                    request=AttachmentIngestionRequest(
                        kind=AttachmentKind.INVOICE_PDF,
                        source=AttachmentSource.LOCAL_FILE,
                        source_reference=f"source-{transaction_id}",
                        mime_type="application/pdf",
                        captured_at=datetime(2026, 3, 1 + index, 9, 0, tzinfo=UTC),
                        bucket_id=_SERVICE_BUCKET_ID,
                        link_transaction_ids=(transaction_id,),
                    ),
                )
                attachment_id = attachment.attachment_id
            return load_attachment(store, attachment_id).linked_transaction_ids

    forward = _ingest(("tx-A", "tx-B"), tmp_path / "forward")
    reversed_order = _ingest(("tx-B", "tx-A"), tmp_path / "reversed")

    assert set(forward) == set(reversed_order) == {"tx-A", "tx-B"}


def test_repeated_identical_ingestion_is_a_stable_no_op(tmp_path: Path) -> None:
    """Re-ingesting the same observation twice must not grow or alter the manifest."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SERVICE_BUCKET_ID):
        store = AttachmentStore()
        data = b"%PDF-1.4\nidempotent same-byte evidence\n%%EOF"
        first = add_attachment(
            store,
            content=AttachmentBytesContent(data=data),
            request=AttachmentIngestionRequest(
                kind=AttachmentKind.INVOICE_PDF,
                source=AttachmentSource.LOCAL_FILE,
                source_reference="source-A",
                mime_type="application/pdf",
                captured_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
                bucket_id=_SERVICE_BUCKET_ID,
                link_transaction_ids=("tx-A",),
            ),
        )
        after_first = load_attachment(store, first.attachment_id)
        add_attachment(
            store,
            content=AttachmentBytesContent(data=data),
            request=AttachmentIngestionRequest(
                kind=AttachmentKind.INVOICE_PDF,
                source=AttachmentSource.LOCAL_FILE,
                source_reference="source-A",
                mime_type="application/pdf",
                captured_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
                bucket_id=_SERVICE_BUCKET_ID,
                link_transaction_ids=("tx-A",),
            ),
        )
        after_third = load_attachment(store, after_first.attachment_id)

    assert after_third == after_first
    assert after_third.linked_transaction_ids == ("tx-A",)
