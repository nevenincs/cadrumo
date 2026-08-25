"""Real secure-store CLI journey from Drive attachment to reviewed invoice."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.storage import AttachmentStore
from ....core.bucket_pointer import resolve_active_bucket_id
from ....domain.attachments import (
    AttachmentBytesContent,
    AttachmentIngestionRequest,
    AttachmentKind,
    AttachmentSource,
    add_attachment,
)
from ._ledger_ux_support import _invoke, _open_bucket_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_open_bucket_session"]

_FACTURAE = (
    Path(__file__).resolve().parents[3]
    / "application"
    / "ledger"
    / "tests"
    / "_evidence_corpus"
    / "facturae_32_recargo_invoice.xml"
)
_DRIVE_FILE_ID = "1AbcDEfgHIjkLMnoPQRstuVWxyz12345"


def _drive_attachment(data: bytes, *, name: str = "invoice.xml") -> str:
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    attachment = add_attachment(
        AttachmentStore(),
        content=AttachmentBytesContent(data=data),
        request=AttachmentIngestionRequest(
            kind=AttachmentKind.DRIVE_DOCUMENT,
            source=AttachmentSource.GOOGLE_DRIVE,
            source_reference=f"https://drive.google.com/file/d/{_DRIVE_FILE_ID}",
            mime_type="application/xml",
            captured_at=datetime(2026, 8, 23, 10, 30, tzinfo=UTC),
            bucket_id=bucket_id,
            metadata={"drive_file_name": name, "secret_material": "must-not-leak"},
            notes="operator-private note",
        ),
    )
    return attachment.attachment_id


def test_drive_attachment_is_queued_inspectable_and_confirmed_once() -> None:
    attachment_id = _drive_attachment(_FACTURAE.read_bytes())
    assert _drive_attachment(_FACTURAE.read_bytes(), name="same-content-again.xml") == attachment_id

    queued = _invoke(["--format", "json", "app", "ledger", "evidence", "attachment-queue"])
    assert queued.exit_code == 0, queued.output
    queue_result = json.loads(queued.output)["result"]
    assert queue_result["count"] == 1
    assert queue_result["rows"][0]["attachment_id"] == attachment_id
    assert queue_result["rows"][0]["source"] == "GOOGLE_DRIVE"

    viewed = _invoke(
        ["--format", "json", "app", "ledger", "evidence", "attachment-view", attachment_id],
    )
    assert viewed.exit_code == 0, viewed.output
    view_result = json.loads(viewed.output)["result"]
    assert view_result["sha256"] == attachment_id
    assert view_result["provider_locator"] == _DRIVE_FILE_ID
    assert "secret_material" not in viewed.output
    assert "operator-private" not in viewed.output

    extracted = _invoke(
        ["--format", "json", "app", "ledger", "evidence", "extract", "--attachment-id", attachment_id],
    )
    assert extracted.exit_code == 0, extracted.output
    assert json.loads(extracted.output)["result"]["invoice_number"] == "FAC-2024-0007"

    command = [
        "--format",
        "json",
        "app",
        "ledger",
        "evidence",
        "confirm",
        "--attachment-id",
        attachment_id,
        "--kind",
        "received",
        "--country-code",
        "ES",
    ]
    first = _invoke(command)
    assert first.exit_code == 0, first.output
    first_result = json.loads(first.output)["result"]
    assert first_result["created"] is True

    repeated = _invoke(command)
    assert repeated.exit_code == 0, repeated.output
    assert json.loads(repeated.output)["result"]["created"] is False

    after = _invoke(["--format", "json", "app", "ledger", "evidence", "attachment-queue"])
    assert json.loads(after.output)["result"] == {"bucket_id": queue_result["bucket_id"], "count": 0, "rows": []}
    traced = _invoke(
        ["--format", "json", "app", "ledger", "evidence", "attachment-view", attachment_id],
    )
    traced_result = json.loads(traced.output)["result"]
    assert traced_result["pending_review"] is False
    assert traced_result["linked_invoice_ids"] == [first_result["invoice_id"]]

    # A later repeat pull of the same bytes must preserve the invoice link and
    # must not put the already-reviewed document back into the queue.
    assert _drive_attachment(_FACTURAE.read_bytes()) == attachment_id
    repeated_pull_queue = _invoke(
        ["--format", "json", "app", "ledger", "evidence", "attachment-queue"],
    )
    assert json.loads(repeated_pull_queue.output)["result"]["count"] == 0


def test_unsupported_drive_content_refuses_without_leaving_the_queue() -> None:
    attachment_id = _drive_attachment(b"not an invoice document", name="unsupported.bin")

    extracted = _invoke(
        ["--format", "json", "app", "ledger", "evidence", "extract", "--attachment-id", attachment_id],
    )

    assert extracted.exit_code != 0, extracted.output
    assert "document" in extracted.output.lower() or "media" in extracted.output.lower()
    queued = _invoke(["--format", "json", "app", "ledger", "evidence", "attachment-queue"])
    assert json.loads(queued.output)["result"]["rows"][0]["attachment_id"] == attachment_id
