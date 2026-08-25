"""Hostile locator coverage for the attachment review projection."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....domain.attachments import Attachment, AttachmentKind, AttachmentSource
from ..attachment_review import _project

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DIGEST = "a" * 64
_FILE_ID = "1AbcDEfgHIjkLMnoPQRstuVWxyz12345"


def _project_locator(reference: str) -> str:
    attachment = Attachment(
        attachment_id=_DIGEST,
        sha256=_DIGEST,
        kind=AttachmentKind.DRIVE_DOCUMENT,
        source=AttachmentSource.GOOGLE_DRIVE,
        source_reference=reference,
        mime_type="application/pdf",
        bytes_size=42,
        captured_at=datetime(2026, 8, 23, tzinfo=UTC),
    )
    return _project(attachment).provider_locator


def test_only_canonical_secret_free_drive_url_exposes_the_file_id() -> None:
    assert _project_locator(f"https://drive.google.com/file/d/{_FILE_ID}") == _FILE_ID


@pytest.mark.parametrize(
    "reference",
    (
        f"http://drive.google.com/file/d/{_FILE_ID}",
        f"https://drive.google.com.evil.test/file/d/{_FILE_ID}",
        f"https://user@drive.google.com/file/d/{_FILE_ID}",
        f"https://drive.google.com/file/d/{_FILE_ID}?access_token=secret",
        f"https://drive.google.com/file/d/{_FILE_ID}#access_token=secret",
        f"https://drive.google.com/file/d/{_FILE_ID}/view",
        "https://drive.google.com/file/d/not-a-drive-reference",
    ),
)
def test_hostile_or_noncanonical_locator_is_never_reflected(reference: str) -> None:
    assert _project_locator(reference) == "not-exposed"
