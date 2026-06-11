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
from googleapiclient.errors import HttpError
from httplib2 import Response

from .....domain.attachments import AttachmentSource
from ....outbound.storage._errors import OutboundStoragePermissionError, OutboundStorageValidationError
from .._document_link_resolver import _download_drive_file_from_service, parse_drive_file_id, resolve_document_link

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_FILE_ID = "1AbcDEfgHIjkLMnoPQRstuVWxyz12345"


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        (f"https://drive.google.com/file/d/{_FILE_ID}/view", _FILE_ID),
        (f"https://drive.google.com/open?id={_FILE_ID}", _FILE_ID),
        (f"https://docs.google.com/spreadsheets/d/{_FILE_ID}/edit#gid=0", _FILE_ID),
        (_FILE_ID, _FILE_ID),
        ("  " + _FILE_ID + "  ", _FILE_ID),
        ("not-a-drive-reference", None),
        ("short", None),
        ("", None),
    ],
)
def test_parse_drive_file_id(reference: str, expected: str | None) -> None:
    assert parse_drive_file_id(reference) == expected


def test_gmail_link_refused_with_gmail_scope() -> None:
    with pytest.raises(OutboundStoragePermissionError) as excinfo:
        resolve_document_link(source=AttachmentSource.GMAIL, reference="anything", credentials=None)
    assert excinfo.value.context is not None
    assert excinfo.value.context["required_scope"] == "https://www.googleapis.com/auth/gmail.readonly"


def test_external_url_refused_with_drive_readonly_scope() -> None:
    with pytest.raises(OutboundStoragePermissionError) as excinfo:
        resolve_document_link(
            source=AttachmentSource.URL, reference="https://example.com/justificante.pdf", credentials=None,
        )
    assert excinfo.value.context is not None
    assert excinfo.value.context["required_scope"] == "https://www.googleapis.com/auth/drive.readonly"


def test_local_file_source_refused_as_not_remote() -> None:
    with pytest.raises(OutboundStorageValidationError):
        resolve_document_link(source=AttachmentSource.LOCAL_FILE, reference="local-store/x.pdf", credentials=None)


def test_drive_link_without_id_is_validation_error() -> None:
    with pytest.raises(OutboundStorageValidationError):
        resolve_document_link(source=AttachmentSource.GOOGLE_DRIVE, reference="no-id-here", credentials=None)


class _InMemoryDriveRequest:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def execute(self) -> bytes:
        return self._payload


class _InMemoryDriveFiles:
    def __init__(self, payload: bytes, recorder: dict[str, object]) -> None:
        self._payload = payload
        self._recorder = recorder

    def get_media(self, *, fileId: str) -> _InMemoryDriveRequest:  # noqa: N803 - Google API kwarg
        self._recorder["file_id"] = fileId
        return _InMemoryDriveRequest(self._payload)


class _InMemoryDriveResource:
    def __init__(self, payload: bytes, recorder: dict[str, object]) -> None:
        self._files = _InMemoryDriveFiles(payload, recorder)

    def files(self) -> _InMemoryDriveFiles:
        return self._files


def test_drive_download_preserves_google_media_bytes() -> None:
    recorder: dict[str, object] = {}
    payload = b"%PDF-1.4 justificante bytes"
    service = _InMemoryDriveResource(payload, recorder)

    out = _download_drive_file_from_service(_FILE_ID, service)
    assert out == payload
    assert recorder["file_id"] == _FILE_ID


def test_drive_403_surfaces_drive_readonly_scope() -> None:
    class _Files:
        def get_media(self, *, fileId: str):  # noqa: N803 - Google API kwarg
            class _Req:
                def execute(self) -> bytes:
                    raise HttpError(Response({"status": "403", "reason": "Forbidden"}), b"{}")

            return _Req()

    class _Svc:
        def files(self) -> _Files:
            return _Files()

    with pytest.raises(OutboundStoragePermissionError) as excinfo:
        _download_drive_file_from_service(_FILE_ID, _Svc())
    assert excinfo.value.context is not None
    assert excinfo.value.context["required_scope"] == "https://www.googleapis.com/auth/drive.readonly"
