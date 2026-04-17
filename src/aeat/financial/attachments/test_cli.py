"""CLI smoke tests for ``aeat attachments``."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from ...cli import app as root_app
from . import AttachmentKind, AttachmentSource, AttachmentStore

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]

_RUNNER = CliRunner()


def _write_source(tmp_path: Path, name: str, data: bytes) -> Path:
    target = tmp_path / name
    target.write_bytes(data)
    return target


def _invoke(args: list[str], store_root: Path) -> Result:
    return _RUNNER.invoke(root_app, args, env={"AEAT_ATTACHMENTS_DIR": str(store_root)})


def test_attachments_add_persists_manifest_and_blob(tmp_path: Path) -> None:
    """`aeat attachments add` should persist both the blob and the manifest."""
    store_root = tmp_path / "store"
    source = _write_source(tmp_path, "invoice.pdf", b"pdf-bytes")

    result = _invoke(
        [
            "attachments",
            "add",
            str(source),
            "--kind",
            AttachmentKind.INVOICE_PDF.value,
            "--source",
            AttachmentSource.LOCAL_FILE.value,
            "--mime-type",
            "application/pdf",
            "--link-tx",
            "tx-1",
            "--link-invoice",
            "inv-1",
            "--metadata",
            "gmail_id=abc123",
            "--notes",
            "first ingest",
        ],
        store_root,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    digest = hashlib.sha256(b"pdf-bytes").hexdigest()
    assert payload["attachment_id"] == digest
    assert payload["sha256"] == digest
    assert payload["kind"] == "INVOICE_PDF"
    assert payload["linked_transaction_ids"] == ["tx-1"]
    assert payload["linked_invoice_ids"] == ["inv-1"]
    assert payload["metadata"] == {"gmail_id": "abc123"}
    store = AttachmentStore.at(store_root)
    assert store.blob_path(digest).read_bytes() == b"pdf-bytes"
    assert store.manifest_path(digest).exists()


def test_attachments_add_merges_links_on_re_ingest(tmp_path: Path) -> None:
    """Re-ingesting the same file must merge link sets in the manifest."""
    store_root = tmp_path / "store"
    source = _write_source(tmp_path, "invoice.pdf", b"pdf-bytes")

    first = _invoke(
        ["attachments", "add", str(source), "--link-tx", "tx-1"],
        store_root,
    )
    assert first.exit_code == 0, first.output
    second = _invoke(
        ["attachments", "add", str(source), "--link-tx", "tx-2", "--link-invoice", "inv-1"],
        store_root,
    )
    assert second.exit_code == 0, second.output
    final = json.loads(second.stdout)
    assert final["linked_transaction_ids"] == ["tx-1", "tx-2"]
    assert final["linked_invoice_ids"] == ["inv-1"]


def test_attachments_list_filters_by_linked_to(tmp_path: Path) -> None:
    """`aeat attachments list --linked-to` should filter output."""
    store_root = tmp_path / "store"
    first = _write_source(tmp_path, "a.pdf", b"a-bytes")
    second = _write_source(tmp_path, "b.pdf", b"b-bytes")
    first_add = _invoke(["attachments", "add", str(first), "--link-tx", "tx-1"], store_root)
    second_add = _invoke(["attachments", "add", str(second), "--link-invoice", "inv-9"], store_root)
    assert first_add.exit_code == 0
    assert second_add.exit_code == 0

    filtered = _invoke(["attachments", "list", "--linked-to", "tx-1"], store_root)
    assert filtered.exit_code == 0, filtered.output
    first_digest = hashlib.sha256(b"a-bytes").hexdigest()
    second_digest = hashlib.sha256(b"b-bytes").hexdigest()
    assert first_digest in filtered.output
    assert second_digest not in filtered.output


def test_attachments_show_prints_manifest_json(tmp_path: Path) -> None:
    """`aeat attachments show <id>` should emit the manifest JSON."""
    store_root = tmp_path / "store"
    source = _write_source(tmp_path, "x.pdf", b"x-bytes")
    add_result = _invoke(["attachments", "add", str(source)], store_root)
    assert add_result.exit_code == 0
    digest = hashlib.sha256(b"x-bytes").hexdigest()

    show_result = _invoke(["attachments", "show", digest], store_root)
    assert show_result.exit_code == 0, show_result.output
    payload = json.loads(show_result.stdout)
    assert payload["attachment_id"] == digest


def test_attachments_show_reports_missing_attachment_cleanly(tmp_path: Path) -> None:
    """Show must exit cleanly with code 2 when the manifest is absent."""
    store_root = tmp_path / "store"
    digest = "a" * 64
    result = _invoke(["attachments", "show", digest], store_root)
    assert result.exit_code == 2
    assert "attachment manifest not found" in result.output


def test_attachments_add_rejects_metadata_without_equals(tmp_path: Path) -> None:
    """--metadata must reject entries missing the ``=`` separator."""
    store_root = tmp_path / "store"
    source = _write_source(tmp_path, "x.pdf", b"x-bytes")
    result = _invoke(
        ["attachments", "add", str(source), "--metadata", "invalid-entry"],
        store_root,
    )
    assert result.exit_code == 2
    assert "--metadata entry must be key=value" in result.output


def test_attachments_add_rejects_duplicate_metadata_keys(tmp_path: Path) -> None:
    """Duplicate metadata keys within one invocation must exit with code 2."""
    store_root = tmp_path / "store"
    source = _write_source(tmp_path, "x.pdf", b"x-bytes")
    result = _invoke(
        [
            "attachments",
            "add",
            str(source),
            "--metadata",
            "k=v1",
            "--metadata",
            "k=v2",
        ],
        store_root,
    )
    assert result.exit_code == 2
    assert "--metadata key repeated" in result.output
