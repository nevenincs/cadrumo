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
from .._service import (
    add_attachment,
    list_attachments,
    load_attachment,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_add_and_load_attachment_roundtrips_through_real_store(tmp_path: Path) -> None:
    """add_attachment persists; load_attachment reads back identical metadata."""

    payload = b"Hello world. This is the test attachment body."
    source_file = tmp_path / "doc.txt"
    source_file.write_bytes(payload)

    with isolated_runtime_profile(tmp_path=tmp_path):
        store = AttachmentStore()
        added = add_attachment(
            store,
            path=source_file,
            kind=AttachmentKind.OTHER,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="test-doc",
            mime_type="text/plain",
            captured_at=datetime.now(UTC),
        )
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

        a = add_attachment(
            store,
            path=first,
            kind=AttachmentKind.OTHER,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="first",
            mime_type="text/plain",
            captured_at=datetime.now(UTC),
        )
        b = add_attachment(
            store,
            path=second,
            kind=AttachmentKind.OTHER,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="second",
            mime_type="text/plain",
            captured_at=datetime.now(UTC),
        )
        rows = list_attachments(store)
        ids = {row.attachment_id for row in rows}
        assert a.attachment_id in ids
        assert b.attachment_id in ids
