"""Tests for the attachment service helpers."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.storage.attachment import AttachmentStore
from ....tests.secure_sql import isolated_runtime_profile
from .._enums import AttachmentKind, AttachmentSource
from .._errors import AttachmentNotFoundError
from .._models import Attachment
from .._service import (
    add_attachment,
    link_attachment_invoice,
    list_attachments,
    load_attachment,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CAPTURED_AT = datetime(2026, 6, 30, 9, 0, 0, tzinfo=UTC)


def _add_text_attachment(store: AttachmentStore, path: Path, *, source_reference: str) -> Attachment:
    return add_attachment(
        store,
        path=path,
        kind=AttachmentKind.OTHER,
        source=AttachmentSource.LOCAL_FILE,
        source_reference=source_reference,
        mime_type="text/plain",
        captured_at=_CAPTURED_AT,
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
