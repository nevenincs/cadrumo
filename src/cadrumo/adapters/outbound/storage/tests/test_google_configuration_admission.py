"""Canonical Google boundary renewals and probe acknowledgements with controlled transport."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from google.auth.transport.requests import Request

from .....application.user_profile.access_contracts import AccessDenialCode
from .....application.user_profile.access_errors import ProfileAccessRefusedError
from .....core.errors.error_codes import get_registered_error_code
from .....tests.google_credentials import unused_google_credentials
from ....persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...google.artifact_receipt_store import GoogleArtifactReceiptStore
from ...google.errors import GoogleAuthScopeInsufficientError
from ...google.google_configuration_admission import admitted_google_auth_request
from ...google.oauth_flow import credentials_to_records
from ...google.records import REQUIRED_SCOPES
from ...google.root_folder import ensure_root_folder
from ...google.tests.drive_files_server import drive_files_endpoint
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


@pytest.mark.parametrize("refuse_create", [False, True])
def test_probe_has_fresh_identity_admission_and_balanced_actual_acknowledgements(
    tmp_path: Path, refuse_create: bool
) -> None:
    profile_id = UUID("1abc0000-0000-4000-8000-000000000001")
    boundary = _Boundary()
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(profile_id)) as profile,
        drive_files_endpoint() as endpoint,
    ):
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=profile_id)
        root_id = ensure_root_folder(endpoint.service, profile=str(profile_id), receipts=receipts)
        provider = drive.GoogleDriveProvider(
            credentials=unused_google_credentials(),
            root_folder_id=root_id,
            vault_folder_name="vault",
            before_handoff=boundary.before,
            acknowledged=boundary.acknowledged,
            receipts=receipts,
        )
        provider._service = endpoint.service
        if refuse_create:
            boundary.refuse = "files.create"
            with pytest.raises(ProfileAccessRefusedError):
                provider.probe()
            assert "files.delete" not in endpoint.calls
        else:
            report = provider.probe()
            assert report.reachable and report.writable and report.root_folder_present
            assert [call for call in endpoint.calls if call == "files.delete"] == ["files.delete"]
            assert ("files.create", True) in boundary.completed
            assert ("files.delete", True) in boundary.completed
        assert not boundary.pending
        assert ("drive.files.get.admission", False) in boundary.completed


def test_google_auth_transport_renews_each_actual_call_and_denial_is_outside_http_translation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary = _Boundary()
    calls: list[str] = []

    def canonical_request(self: Request, url: str, **_kwargs: object) -> object:
        assert boundary.pending[-1] == ("oauth.identity-verification", False)
        calls.append(url)
        return object()

    monkeypatch.setattr(Request, "__call__", canonical_request)
    request = admitted_google_auth_request(
        before_handoff=boundary.before, acknowledged=boundary.acknowledged, action="oauth.identity-verification"
    )
    request("https://synthetic.invalid/one")
    request("https://synthetic.invalid/two")
    assert calls == ["https://synthetic.invalid/one", "https://synthetic.invalid/two"]
    assert boundary.completed == [("oauth.identity-verification", False), ("oauth.identity-verification", False)]
    boundary.refuse = "oauth.identity-verification"
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
            client_id="synthetic-client.apps.googleusercontent.com",
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
