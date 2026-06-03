"""Document-link resolution under the minimal-scope posture (follow-up S03).

The integration deliberately requests only the non-sensitive ``drive.file``
scope. This gate locks the resolver's contract offline, with no network:

- ``parse_drive_file_id`` recovers a Drive file id from the three recorded link
  shapes (``/file/d/<id>``, ``?id=<id>``, bare id) and returns ``None`` otherwise;
- a ``GOOGLE_DRIVE`` link with a recognisable id dispatches to the Drive download
  path (here a fake service, since real downloads are operator-tested);
- Gmail links, arbitrary external URLs, and ``drive.file``-unreachable Drive files
  are refused with a typed scope error naming the sensitive scope the operator
  would need to grant — never silently swallowed.
"""

from __future__ import annotations

import pytest

from ....domain.attachments import AttachmentSource
from ...outbound.storage._errors import OutboundStoragePermissionError, OutboundStorageValidationError
from . import _document_link_resolver as resolver
from ._document_link_resolver import parse_drive_file_id, resolve_document_link

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]

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
    assert excinfo.value.context["required_scope"] == "https://www.googleapis.com/auth/gmail.readonly"


def test_external_url_refused_with_drive_readonly_scope() -> None:
    with pytest.raises(OutboundStoragePermissionError) as excinfo:
        resolve_document_link(
            source=AttachmentSource.URL, reference="https://example.com/justificante.pdf", credentials=None
        )
    assert excinfo.value.context["required_scope"] == "https://www.googleapis.com/auth/drive.readonly"


def test_local_file_source_refused_as_not_remote() -> None:
    with pytest.raises(OutboundStorageValidationError):
        resolve_document_link(source=AttachmentSource.LOCAL_FILE, reference="local-store/x.pdf", credentials=None)


def test_drive_link_without_id_is_validation_error() -> None:
    with pytest.raises(OutboundStorageValidationError):
        resolve_document_link(source=AttachmentSource.GOOGLE_DRIVE, reference="no-id-here", credentials=None)


class _FakeRequest:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def execute(self) -> bytes:
        return self._payload


class _FakeFiles:
    def __init__(self, payload: bytes, recorder: dict[str, object]) -> None:
        self._payload = payload
        self._recorder = recorder

    def get_media(self, *, fileId: str) -> _FakeRequest:  # noqa: N803 — Google API kwarg name
        self._recorder["file_id"] = fileId
        return _FakeRequest(self._payload)


class _FakeService:
    def __init__(self, payload: bytes, recorder: dict[str, object]) -> None:
        self._files = _FakeFiles(payload, recorder)

    def files(self) -> _FakeFiles:
        return self._files


def test_drive_link_with_id_downloads_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder: dict[str, object] = {}
    payload = b"%PDF-1.4 fake justificante bytes"
    monkeypatch.setattr(resolver, "_drive_service", lambda credentials: _FakeService(payload, recorder))

    out = resolve_document_link(
        source=AttachmentSource.GOOGLE_DRIVE,
        reference=f"https://drive.google.com/file/d/{_FILE_ID}/view",
        credentials=object(),
    )
    assert out == payload
    assert recorder["file_id"] == _FILE_ID


class _ForbiddenResp:
    status = 403


def test_drive_403_surfaces_drive_readonly_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Files:
        def get_media(self, *, fileId: str):  # noqa: N803
            class _Req:
                def execute(self) -> bytes:
                    err = Exception("HttpError 403")
                    err.resp = _ForbiddenResp()  # type: ignore[attr-defined]
                    raise err

            return _Req()

    class _Svc:
        def files(self) -> _Files:
            return _Files()

    monkeypatch.setattr(resolver, "_drive_service", lambda credentials: _Svc())

    with pytest.raises(OutboundStoragePermissionError) as excinfo:
        resolve_document_link(
            source=AttachmentSource.GOOGLE_DRIVE,
            reference=f"https://drive.google.com/file/d/{_FILE_ID}/view",
            credentials=object(),
        )
    assert excinfo.value.context["required_scope"] == "https://www.googleapis.com/auth/drive.readonly"
