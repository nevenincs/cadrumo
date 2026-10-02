"""Canonical local Google records reopen encrypted; no Google/browser/IAM is contacted."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from ...adapters.outbound.google.google_configuration_refusal import google_configuration_refusal_error
from ...adapters.outbound.google.records import REQUIRED_SCOPES, OAuthMetadata, OAuthToken
from ...adapters.outbound.google.session_store import (
    load_client,
    load_drive_config,
    load_metadata,
    load_token,
    save_metadata,
    save_token,
)
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile, read_db_at_rest_bytes
from ...application.user_profile import google_configuration_operation_contracts as contracts
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.google_configuration_operation_refusal import GoogleConfigurationRefusedError
from ...core.google_credential_source import GoogleCredentialSourceKind
from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from .. import google_configuration_operation_composition as composition

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_PROFILE = UUID("49494949-4949-4494-8494-494949494949")
_CLIENT_CREDENTIAL = "synthetic-cloud-client-secret"
_REFRESH_CREDENTIAL = "synthetic-refresh-secret"
_OAUTH_ENDPOINT = "https://oauth2.googleapis.com/token"


def _client_bytes() -> bytes:
    return json.dumps(
        {
            "installed": {
                "client_id": "synthetic-client.apps.googleusercontent.com",
                "client_secret": _CLIENT_CREDENTIAL,
                "project_id": "synthetic-project",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": _OAUTH_ENDPOINT,
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": ["http://localhost"],
            }
        }
    ).encode()


def test_composed_local_leaves_preserve_full_records_and_idempotent_logout(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_provider(**_kwargs: object):
        pytest.fail("local configuration acquired a provider")

    monkeypatch.setattr(composition, "get_storage_provider", forbidden_provider)
    commits: list[bool] = []

    def commit[T](save: Callable[[], T], *, changed: Callable[[T], bool]) -> T:
        result = save()
        commits.append(changed(result))
        return result

    def no_handoff(action: str, *, writes: bool = False) -> None:
        assert action == "google.oauth-client-acquisition" and not writes

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile:
        ports = composition.build_google_configuration_operation_ports(
            profile_id=_PROFILE, operation=authority_operation
        )
        assert ports.operation is authority_operation

        def run(request: contracts.GoogleConfigurationRequest, secret: memoryview | None = None):
            return ports.run(
                request,
                secret=secret,
                commit=commit,
                before_handoff=no_handoff,
                acknowledged=no_handoff,
                terminal_admission=None,
            )

        default = run(contracts.GoogleCredentialSourceViewRequest(profile_id=_PROFILE))
        assert isinstance(default, contracts.GoogleCredentialSourceViewProjection)
        assert default.kind is GoogleCredentialSourceKind.OAUTH_DESKTOP and not default.configured
        selected = run(
            contracts.GoogleCredentialSourceSetRequest(
                profile_id=_PROFILE,
                kind=GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION,
                target_principal=" synthetic@project.iam.gserviceaccount.com ",
                scopes=("https://www.googleapis.com/auth/drive.file",),
                delegates=("delegate@project.iam.gserviceaccount.com",),
                lifetime_seconds=600,
            )
        )
        inspected = run(contracts.GoogleCredentialSourceViewRequest(profile_id=_PROFILE))
        assert isinstance(selected, contracts.GoogleCredentialSourceSetProjection)
        assert isinstance(inspected, contracts.GoogleCredentialSourceViewProjection)
        assert (
            inspected.configured
            and inspected.target_principal == selected.target_principal == "synthetic@project.iam.gserviceaccount.com"
        )
        assert inspected.target_scopes == selected.target_scopes and inspected.delegates == selected.delegates
        assert inspected.lifetime_s == 600
        root = run(contracts.GoogleFolderSetRequest(profile_id=_PROFILE, folder_id=" synthetic-root "))
        assert isinstance(root, contracts.GoogleFolderSetProjection) and root.root_folder_id == "synthetic-root"
        assert load_drive_config(str(_PROFILE)) is not None
        encoded = _client_bytes()
        registered = run(
            contracts.GoogleRegisterRequest(
                profile_id=_PROFILE,
                client_json_path=str(tmp_path / "client.json"),
                client_json_sha256=sha256_hex(encoded),
            ),
            memoryview(encoded),
        )
        assert isinstance(registered, contracts.GoogleRegisterProjection)
        assert registered.client_id == "synthetic-client.apps.googleusercontent.com"
        stored_client = load_client(str(_PROFILE))
        assert stored_client is not None and stored_client.client_secret == _CLIENT_CREDENTIAL
        now = datetime.now(UTC)
        # Canonical fixture setup supplies a previously acknowledged session;
        # the refresh-only leaf still performs its original metadata inspection.
        save_token(
            str(_PROFILE),
            OAuthToken(refresh_token=_REFRESH_CREDENTIAL, token_uri=_OAUTH_ENDPOINT),
        )
        save_metadata(
            str(_PROFILE),
            OAuthMetadata(
                account_email="synthetic@example.invalid",
                granted_scopes=REQUIRED_SCOPES,
                issued_at=now,
                last_refresh_at=now,
                reauth_required=True,
            ),
        )
        refreshed = run(contracts.GoogleLoginRequest(profile_id=_PROFILE, refresh_only=True))
        assert isinstance(refreshed, contracts.GoogleLoginProjection)
        assert (
            refreshed.mode == "refresh-only"
            and refreshed.account_email == "synthetic@example.invalid"
            and refreshed.granted_scopes == ()
        )
        status = run(contracts.GoogleStatusRequest(profile_id=_PROFILE))
        assert isinstance(status, contracts.GoogleStatusProjection)
        assert status.client_registered and status.session_present and status.granted_scopes == REQUIRED_SCOPES
        assert (
            status.issued_at == now.isoformat() and status.last_refresh_at == now.isoformat() and status.reauth_required
        )
        at_rest = read_db_at_rest_bytes(profile.paths.database_file)
        assert b"synthetic-cloud-client-secret" not in at_rest and b"synthetic-refresh-secret" not in at_rest
        first = run(contracts.GoogleLogoutRequest(profile_id=_PROFILE))
        second = run(contracts.GoogleLogoutRequest(profile_id=_PROFILE))
        assert isinstance(first, contracts.GoogleLogoutProjection) and first.token_removed and first.metadata_removed
        assert (
            isinstance(second, contracts.GoogleLogoutProjection)
            and not second.token_removed
            and not second.metadata_removed
        )
        assert (
            load_client(str(_PROFILE)) == stored_client
            and load_token(str(_PROFILE)) is None
            and load_metadata(str(_PROFILE)) is None
        )
        assert commits == [True, True, True, True, False]
        with pytest.raises(ProfileAccessRefusedError):
            composition.build_google_configuration_operation_ports(profile_id=uuid4(), operation=authority_operation)


def test_register_digest_mismatch_is_closed_prewrite_and_restores_original_human_error(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    def forbidden_commit[T](save: Callable[[], T], *, changed: Callable[[T], bool]) -> T:
        pytest.fail("source mismatch reached actual credential save")

    def forbidden_handoff(action: str, *, writes: bool = False) -> None:
        pytest.fail("source mismatch acquired provider credentials")

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)):
        ports = composition.build_google_configuration_operation_ports(
            profile_id=_PROFILE, operation=authority_operation
        )
        with pytest.raises(GoogleConfigurationRefusedError) as caught:
            ports.run(
                contracts.GoogleRegisterRequest(
                    profile_id=_PROFILE, client_json_path=str(tmp_path / "client.json"), client_json_sha256="f" * 64
                ),
                secret=memoryview(_client_bytes()),
                commit=forbidden_commit,
                before_handoff=forbidden_handoff,
                acknowledged=forbidden_handoff,
                terminal_admission=None,
            )
        refusal = caught.value.projection
        assert (
            refusal.provider_code == "REFUSED_GOOGLE_VALIDATION" and refusal.facts.error_type == "SourceDigestMismatch"
        )
        original = google_configuration_refusal_error(
            refusal,
            operation_id="a" * 64,
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.REFUSED,
            refusal_code="REFUSED_GOOGLE_CONFIGURATION",
        )
        assert original.code.code == "REFUSED_GOOGLE_VALIDATION"
        assert original.translated_message == "cli.config.google.detail.client_json_invalid"
        assert original.context is not None and original.context["path"] == str(tmp_path / "client.json")
        assert original.context["operation_id"] == "a" * 64 and original.context["effect"] == "none"
        assert "synthetic-cloud-client-secret" not in refusal.model_dump_json()
        assert load_client(str(_PROFILE)) is None
