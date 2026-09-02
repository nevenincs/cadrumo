"""Adverse-condition tests for remote ciphertext mirror inspections."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....persistence.storage.sql.secure_objects import SecureObjectRawRow
from ..local import LocalFileSystemProvider
from ..mirror_manifest import (
    build_remote_mirror_namespace_manifest,
    inspect_remote_mirror_download,
    inspect_remote_mirror_upload,
    put_remote_mirror_namespace_manifest,
)
from ..records import RemoteMirrorIssueKind, RemoteMirrorObjectManifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_NAMESPACE = "aeat.remote.mirror.adverse"
_NOW = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)


def test_remote_mirror_upload_inspection_detects_manifest_partial_upload(tmp_path: Path) -> None:
    first_row = _row("first", b"first-ciphertext", revision="a" * 64)
    second_row = _row("second", b"second-ciphertext", revision="b" * 64)
    local_manifest = build_remote_mirror_namespace_manifest(_NAMESPACE, (first_row, second_row))
    remote_manifest = build_remote_mirror_namespace_manifest(_NAMESPACE, (first_row,))
    first_entry, second_entry = local_manifest.objects
    provider = LocalFileSystemProvider(tmp_path / "mirror")
    put_remote_mirror_namespace_manifest(provider, remote_manifest)
    _put_ciphertext(provider, first_entry, first_row.payload)
    _put_ciphertext(provider, second_entry, second_row.payload)

    inspection = inspect_remote_mirror_upload(provider, local_manifest)

    assert inspection.ok is False
    assert len(inspection.issues) == 1
    issue = inspection.issues[0]
    assert issue.kind is RemoteMirrorIssueKind.PARTIAL_UPLOAD
    assert issue.object_key_hmac == second_entry.object_key_hmac


def test_remote_mirror_download_inspection_detects_manifest_partial_download(tmp_path: Path) -> None:
    first_row = _row("first", b"first-ciphertext", revision="a" * 64)
    second_row = _row("second", b"second-ciphertext", revision="b" * 64)
    remote_manifest = build_remote_mirror_namespace_manifest(_NAMESPACE, (first_row, second_row))
    first_entry, second_entry = remote_manifest.objects
    provider = LocalFileSystemProvider(tmp_path / "mirror")
    _put_ciphertext(provider, first_entry, first_row.payload)

    inspection = inspect_remote_mirror_download(provider, remote_manifest)

    assert inspection.ok is False
    assert len(inspection.issues) == 1
    issue = inspection.issues[0]
    assert issue.kind is RemoteMirrorIssueKind.PARTIAL_DOWNLOAD
    assert issue.object_key_hmac == second_entry.object_key_hmac


def test_remote_mirror_upload_inspection_detects_manifest_revision_conflict(tmp_path: Path) -> None:
    local_row = _row(
        "same-object",
        b"local-ciphertext",
        revision="b" * 64,
        previous_revision="a" * 64,
    )
    remote_row = _row(
        "same-object",
        b"remote-ciphertext",
        revision="d" * 64,
        previous_revision="c" * 64,
    )
    local_manifest = build_remote_mirror_namespace_manifest(_NAMESPACE, (local_row,))
    remote_manifest = build_remote_mirror_namespace_manifest(_NAMESPACE, (remote_row,))
    local_entry = local_manifest.objects[0]
    provider = LocalFileSystemProvider(tmp_path / "mirror")
    put_remote_mirror_namespace_manifest(provider, remote_manifest)
    _put_ciphertext(provider, local_entry, local_row.payload)

    inspection = inspect_remote_mirror_upload(provider, local_manifest)

    assert inspection.ok is False
    assert len(inspection.issues) == 1
    issue = inspection.issues[0]
    assert issue.kind is RemoteMirrorIssueKind.REVISION_CONFLICT
    assert issue.object_key_hmac == local_entry.object_key_hmac


def _row(
    object_key: str,
    payload: bytes,
    *,
    revision: str,
    previous_revision: str | None = None,
) -> SecureObjectRawRow:
    return SecureObjectRawRow(
        row_id=1,
        namespace=_NAMESPACE,
        object_key=object_key.encode(),
        classification="financial",
        schema_version=1,
        written_at=_NOW,
        payload=payload,
        revision_id=revision,
        previous_revision_id=previous_revision,
        payload_hash=hashlib.sha256(payload).hexdigest(),
        ciphertext_hash=hashlib.sha256(payload).hexdigest(),
        revision_written_at=_NOW,
    )


def _put_ciphertext(
    provider: LocalFileSystemProvider,
    entry: RemoteMirrorObjectManifest,
    payload: bytes,
) -> None:
    provider.put(
        entry.namespace,
        entry.object_key_hmac,
        payload,
        content_hash=f"sha256-{entry.ciphertext_hash}",
        label="remote-mirror-adverse",
    )
