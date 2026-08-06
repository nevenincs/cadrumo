"""Document-link resolution under the minimal-scope posture (follow-up contract).

The integration deliberately requests only the non-sensitive ``drive.file``
scope. This gate locks the resolver's contract offline, with no network:

- ``parse_drive_file_id`` recovers a Drive file id from the three recorded link
  shapes (``/file/d/<id>``, ``?id=<id>``, bare id) and returns ``None`` otherwise;
- the Drive download path preserves Google ``files.get_media`` byte payloads;
- Gmail links, arbitrary external URLs, and ``drive.file``-unreachable Drive files
  are refused with a typed scope error naming the sensitive scope the operator
  would need to grant — never silently swallowed.
"""

from __future__ import annotations

import pytest

from .....domain.attachments import AttachmentSource
from ...storage import (
    OutboundStoragePermissionError,
    OutboundStorageValidationError,
)
from .._document_link_resolver import _download_drive_file_from_service, parse_drive_file_id, resolve_document_link
from ._drive_media_server import drive_media_endpoint

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_FILE_ID = "1AbcDEfgHIjkLMnoPQRstuVWxyz12345"


def test_parse_drive_file_id_accepts_recorded_shapes_and_rejects_non_ids() -> None:
    cases: tuple[tuple[str, str, str | None], ...] = (
        ("drive file URL", f"https://drive.google.com/file/d/{_FILE_ID}/view", _FILE_ID),
        ("drive open URL", f"https://drive.google.com/open?id={_FILE_ID}", _FILE_ID),
        ("docs spreadsheet URL", f"https://docs.google.com/spreadsheets/d/{_FILE_ID}/edit#gid=0", _FILE_ID),
        ("bare id", _FILE_ID, _FILE_ID),
        ("padded bare id", "  " + _FILE_ID + "  ", _FILE_ID),
        ("hyphenated non-id token", "not-a-drive-reference", None),
        ("short token", "short", None),
        ("empty reference", "", None),
    )

    for label, reference, expected in cases:
        assert parse_drive_file_id(reference) == expected, label


def test_unresolvable_remote_sources_name_required_sensitive_scope() -> None:
    cases: tuple[tuple[AttachmentSource, str, str], ...] = (
        (AttachmentSource.GMAIL, "anything", "https://www.googleapis.com/auth/gmail.readonly"),
        (
            AttachmentSource.URL,
            "https://example.com/justificante.pdf",
            "https://www.googleapis.com/auth/drive.readonly",
        ),
    )

    for source, reference, required_scope in cases:
        with pytest.raises(OutboundStoragePermissionError) as excinfo:
            resolve_document_link(source=source, reference=reference, credentials=None)
        assert excinfo.value.context is not None, source.value
        assert excinfo.value.context["required_scope"] == required_scope


def test_non_resolvable_inputs_are_validation_errors() -> None:
    cases: tuple[tuple[AttachmentSource, str], ...] = (
        (AttachmentSource.LOCAL_FILE, "local-store/x.pdf"),
        (AttachmentSource.GOOGLE_DRIVE, "no-id-here"),
    )

    for source, reference in cases:
        with pytest.raises(OutboundStorageValidationError):
            resolve_document_link(source=source, reference=reference, credentials=None)


def test_drive_download_preserves_google_media_bytes() -> None:
    payload = b"%PDF-1.4 justificante bytes"

    with drive_media_endpoint(payload=payload) as endpoint:
        out = _download_drive_file_from_service(_FILE_ID, endpoint.service)

    assert out == payload
    assert endpoint.requested_paths == [f"/drive/v3/files/{_FILE_ID}?alt=media"]


def test_drive_403_surfaces_drive_readonly_scope() -> None:
    with (
        drive_media_endpoint(payload=b"{}", status=403) as endpoint,
        pytest.raises(OutboundStoragePermissionError) as excinfo,
    ):
        _download_drive_file_from_service(_FILE_ID, endpoint.service)

    assert excinfo.value.context is not None
    assert excinfo.value.context["required_scope"] == "https://www.googleapis.com/auth/drive.readonly"
