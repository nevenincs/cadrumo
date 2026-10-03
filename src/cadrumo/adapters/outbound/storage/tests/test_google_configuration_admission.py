"""Canonical Google boundary renewals and probe acknowledgements with controlled transport."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from google.auth.transport.requests import Request

from .....application.user_profile.access_contracts import AccessDenialCode
from .....application.user_profile.access_errors import ProfileAccessRefusedError
from .....core.errors.error_codes import get_registered_error_code
from .....tests.google_credentials import unused_google_credentials
from ...google.drive_entries import OWNERSHIP_KEY, OWNERSHIP_VALUE
from ...google.errors import GoogleAuthScopeInsufficientError
from ...google.google_configuration_admission import admitted_google_auth_request
from ...google.oauth_flow import credentials_to_records
from ...google.records import REQUIRED_SCOPES
from .. import _google_drive as drive

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _Boundary:
    def __init__(self) -> None:
        self.pending: list[tuple[str, bool]] = []
        self.completed: list[tuple[str, bool]] = []
        self.refuse: str | None = None

    def before(self, action: str, *, writes: bool = False) -> None:
        if action == self.refuse:
            raise ProfileAccessRefusedError(AccessDenialCode.SESSION_INACTIVE)
        self.pending.append((action, writes))

    def acknowledged(self, action: str, *, writes: bool = False) -> None:
        assert self.pending[-1] == (action, writes)
        self.pending.pop()
        self.completed.append((action, writes))


class _Request:
    def __init__(self, call: Callable[[], object]) -> None:
        self.call = call

    def execute(self) -> object:
        return self.call()


class _DriveService:
    """Response-shaped Drive double; the production provider keeps its full algorithm."""

    def __init__(self, boundary: _Boundary, *, malformed_write: bool = False) -> None:
        self.boundary = boundary
        self.malformed_write = malformed_write
        self.file: dict[str, object] | None = None
        self.calls: list[str] = []

    def files(self):
        return self

    def get(self, **_kwargs: object) -> _Request:
        def read():
            assert self.boundary.pending[-1] == ("probe.get_root", False)
            self.calls.append("root")
            return {"id": "root", "mimeType": "application/vnd.google-apps.folder", "trashed": False}

        return _Request(read)

    def list(self, **kwargs: object) -> _Request:
        query = kwargs["q"]
        assert isinstance(query, str)

        def read():
            self.calls.append("list")
            if "'root' in parents" in query:
                return {
                    "files": [
                        {
                            "id": "vault",
                            "name": "cadrumo-vault",
                            "mimeType": "application/vnd.google-apps.folder",
                            "appProperties": {OWNERSHIP_KEY: OWNERSHIP_VALUE},
                        }
                    ]
                }
            if "'vault' in parents" in query:
                return {
                    "files": [
                        {
                            "id": "probe",
                            "name": "_probe",
                            "mimeType": "application/vnd.google-apps.folder",
                            "appProperties": {OWNERSHIP_KEY: OWNERSHIP_VALUE},
                        }
                    ]
                }
            assert "'probe' in parents" in query
            return {"files": [self.file] if self.file is not None else []}

        return _Request(read)

    def create(self, **kwargs: object) -> _Request:
        body = kwargs["body"]
        assert isinstance(body, dict)

        def write():
            assert self.boundary.pending[-1] == ("files.create", True)
            self.calls.append("put")
            self.file = {
                "id": "sentinel",
                "name": body["name"],
                "size": "0",
                "md5Checksum": "d41d8cd98f00b204e9800998ecf8427e",
                "modifiedTime": "malformed" if self.malformed_write else "2026-10-01T12:00:00Z",
                "appProperties": body["appProperties"],
            }
            return self.file

        return _Request(write)

    def delete(self, **kwargs: object) -> _Request:
        assert kwargs["fileId"] == "sentinel"

        def delete():
            assert self.boundary.pending[-1] == ("files.delete", True)
            self.calls.append("delete")
            self.file = None
            return None

        return _Request(delete)


def test_probe_keeps_canonical_sentinel_identity_put_delete_and_positive_write_ack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary = _Boundary()
    service = _DriveService(boundary)
    monkeypatch.setattr(drive, "_service_factory", lambda _credentials: service)
    provider = drive.GoogleDriveProvider(
        credentials=unused_google_credentials(),
        root_folder_id="root",
        vault_folder_name="cadrumo-vault",
        before_handoff=boundary.before,
        acknowledged=boundary.acknowledged,
    )
    report = provider.probe()
    assert report.reachable and report.writable and report.root_folder_present
    assert [call for call in service.calls if call in {"put", "delete"}] == ["put", "delete"]
    assert not boundary.pending
    assert [item for item in boundary.completed if item[1]] == [("files.create", True), ("files.delete", True)]
    assert service.file is None


def test_probe_authority_loss_propagates_before_actual_request_without_provider_translation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary = _Boundary()
    boundary.refuse = "files.create"
    service = _DriveService(boundary)
    monkeypatch.setattr(drive, "_service_factory", lambda _credentials: service)
    provider = drive.GoogleDriveProvider(
        credentials=unused_google_credentials(),
        root_folder_id="root",
        vault_folder_name="cadrumo-vault",
        before_handoff=boundary.before,
        acknowledged=boundary.acknowledged,
    )
    with pytest.raises(ProfileAccessRefusedError):
        provider.probe()
    assert "put" not in service.calls and "delete" not in service.calls
    assert not boundary.pending


def test_malformed_remote_write_never_becomes_positive_provider_ack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary = _Boundary()
    service = _DriveService(boundary, malformed_write=True)
    monkeypatch.setattr(drive, "_service_factory", lambda _credentials: service)
    provider = drive.GoogleDriveProvider(
        credentials=unused_google_credentials(),
        root_folder_id="root",
        vault_folder_name="cadrumo-vault",
        before_handoff=boundary.before,
        acknowledged=boundary.acknowledged,
    )
    report = provider.probe()
    assert report.reachable and not report.writable
    assert boundary.pending == [("files.create", True)]
    assert ("files.create", True) not in boundary.completed and "delete" not in service.calls


def test_google_auth_transport_renews_each_actual_call_and_denial_is_outside_http_translation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary = _Boundary()
    calls: list[str] = []

    def canonical_request(self: Request, url: str, **_kwargs: object) -> object:
        assert boundary.pending[-1] == ("google.iam-mint", False)
        calls.append(url)
        return object()

    monkeypatch.setattr(Request, "__call__", canonical_request)
    request = admitted_google_auth_request(
        before_handoff=boundary.before, acknowledged=boundary.acknowledged, action="google.iam-mint"
    )
    request("https://synthetic.invalid/one")
    request("https://synthetic.invalid/two")
    assert calls == ["https://synthetic.invalid/one", "https://synthetic.invalid/two"]
    assert boundary.completed == [("google.iam-mint", False), ("google.iam-mint", False)]
    boundary.refuse = "google.iam-mint"
    with pytest.raises(ProfileAccessRefusedError):
        request("https://synthetic.invalid/denied")
    assert len(calls) == 2 and not boundary.pending


def test_scope_failure_keeps_original_typed_missing_order_and_registered_code() -> None:
    granted = REQUIRED_SCOPES[:1]
    refresh_value = "synthetic-token"
    issuer_url = "https://oauth2.googleapis.com/token"
    with pytest.raises(GoogleAuthScopeInsufficientError) as caught:
        credentials_to_records(
            refresh_token=refresh_value,
            token_uri=issuer_url,
            account_email="synthetic@example.invalid",
            granted_scopes=granted,
            issued_at=datetime.now(UTC),
        )
    failure = caught.value.scope_failure
    assert failure is not None and failure.missing_scopes == tuple(
        scope for scope in REQUIRED_SCOPES if scope not in granted
    )
    assert failure.account_email == "synthetic@example.invalid"
    assert get_registered_error_code(caught.value).code == "AUTH_GOOGLE_SCOPE_INSUFFICIENT"
