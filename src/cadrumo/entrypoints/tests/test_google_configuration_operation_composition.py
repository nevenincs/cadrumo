"""Canonical local Google records reopen encrypted; no Google/browser/IAM is contacted."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from google.oauth2.credentials import Credentials as OAuthCredentials

from ...adapters.outbound.google.errors import GoogleAuthClientMetadataUnavailableError
from ...adapters.outbound.google.google_configuration_refusal import google_configuration_refusal_error
from ...adapters.outbound.google.records import REQUIRED_SCOPES, DriveConfig, OAuthMetadata, OAuthToken
from ...adapters.outbound.google.session_store import (
    load_drive_config,
    load_metadata,
    load_token,
    save_drive_config,
    save_metadata,
    save_token,
)
from ...adapters.outbound.google.tests.installation_client_support import (
    SYNTHETIC_CLIENT_CREDENTIAL,
    SYNTHETIC_CLIENT_ID,
    synthetic_installation_client,
    use_absent_installation_client,
    use_installation_client,
    use_installation_client_file,
    write_installation_client,
)
from ...adapters.outbound.storage.errors import OutboundStorageConflictError
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile, read_db_at_rest_bytes
from ...application.user_profile import google_configuration_operation_contracts as contracts
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.google_configuration_operation_refusal import GoogleConfigurationRefusedError
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from .. import google_configuration_operation_composition as composition

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_PROFILE = UUID("49494949-4949-4494-8494-494949494949")
_REFRESH_CREDENTIAL = "synthetic-refresh-secret"
_OAUTH_ENDPOINT = "https://oauth2.googleapis.com/token"


def test_composed_local_leaves_preserve_full_records_and_idempotent_logout(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_provider(**_kwargs: object):
        pytest.fail("local configuration acquired a provider")

    monkeypatch.setattr(composition, "get_storage_provider", forbidden_provider)
    use_installation_client(monkeypatch, tmp_path / "installation")
    commits: list[bool] = []

    def commit[T](save: Callable[[], T], *, changed: Callable[[T], bool]) -> T:
        result = save()
        commits.append(changed(result))
        return result

    def forbidden_handoff(action: str, *, writes: bool = False) -> None:
        pytest.fail(f"a local configuration leaf crossed the provider boundary {action}")

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as profile:
        ports = composition.build_google_configuration_operation_ports(
            profile_id=_PROFILE, operation=authority_operation
        )
        assert ports.operation is authority_operation

        def run(request: contracts.GoogleConfigurationRequest):
            return ports.run(
                request,
                commit=commit,
                before_handoff=forbidden_handoff,
                acknowledged=forbidden_handoff,
                terminal_admission=None,
            )

        unconfigured = run(contracts.GoogleFolderViewRequest(profile_id=_PROFILE))
        assert isinstance(unconfigured, contracts.GoogleFolderViewProjection)
        assert unconfigured.configured is False and unconfigured.root_folder_id is None
        # A sign-in is what creates and stores the root folder; this fixture stores one directly.
        save_drive_config(str(_PROFILE), DriveConfig(root_folder_id="synthetic-root"))
        viewed = run(contracts.GoogleFolderViewRequest(profile_id=_PROFILE))
        assert isinstance(viewed, contracts.GoogleFolderViewProjection)
        assert viewed.configured is True and viewed.root_folder_id == "synthetic-root"
        now = datetime.now(UTC)
        # Canonical fixture setup supplies a previously acknowledged session.
        save_token(
            str(_PROFILE),
            OAuthToken(refresh_token=_REFRESH_CREDENTIAL, client_id=SYNTHETIC_CLIENT_ID, token_uri=_OAUTH_ENDPOINT),
        )
        save_metadata(
            str(_PROFILE),
            OAuthMetadata(
                account_email="synthetic@example.invalid",
                granted_scopes=REQUIRED_SCOPES,
                issued_at=now,
            ),
        )
        status = run(contracts.GoogleStatusRequest(profile_id=_PROFILE))
        assert isinstance(status, contracts.GoogleStatusProjection)
        assert status.session_present and status.granted_scopes == REQUIRED_SCOPES
        assert status.issued_at == now.isoformat()
        assert set(status.model_dump()) == {
            "profile_id",
            "session_present",
            "account_email",
            "granted_scopes",
            "issued_at",
        }
        # The installation client is never copied into the profile's store or a result.
        at_rest = read_db_at_rest_bytes(profile.paths.database_file)
        assert SYNTHETIC_CLIENT_CREDENTIAL.encode() not in at_rest and b"synthetic-refresh-secret" not in at_rest
        assert SYNTHETIC_CLIENT_CREDENTIAL not in status.model_dump_json()
        first = run(contracts.GoogleLogoutRequest(profile_id=_PROFILE))
        second = run(contracts.GoogleLogoutRequest(profile_id=_PROFILE))
        assert isinstance(first, contracts.GoogleLogoutProjection) and first.token_removed and first.metadata_removed
        assert (
            isinstance(second, contracts.GoogleLogoutProjection)
            and not second.token_removed
            and not second.metadata_removed
        )
        assert load_token(str(_PROFILE)) is None and load_metadata(str(_PROFILE)) is None
        assert load_drive_config(str(_PROFILE)) is not None
        assert commits == [True, False]
        with pytest.raises(ProfileAccessRefusedError):
            composition.build_google_configuration_operation_ports(profile_id=uuid4(), operation=authority_operation)


@pytest.mark.parametrize(
    ("installed", "message_key", "facts"),
    (
        pytest.param(
            "absent",
            "errors.refused.refused_google_client_metadata_unavailable",
            {"client_metadata_present": False},
            id="no-client-file",
        ),
        pytest.param(
            "invalid",
            "adapters.google.installation_client.errors.client_metadata_invalid",
            {"client_metadata_present": True, "client_metadata_valid": False},
            id="invalid-client-file",
        ),
    ),
)
def test_sign_in_without_usable_installation_client_is_one_closed_prewrite_refusal(
    installed: str,
    message_key: str,
    facts: dict[str, bool],
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Consent preparation and the sign-in leaf refuse alike, before any write or handoff."""

    def forbidden_commit[T](save: Callable[[], T], *, changed: Callable[[T], bool]) -> T:
        pytest.fail("a sign-in without client metadata reached a credential save")

    def forbidden_handoff(action: str, *, writes: bool = False) -> None:
        pytest.fail("a sign-in without client metadata crossed a provider boundary")

    if installed == "absent":
        use_absent_installation_client(monkeypatch, tmp_path / "installation")
    else:
        path = write_installation_client(tmp_path / "installation", synthetic_installation_client())
        document = json.loads(path.read_text(encoding="utf-8"))
        del document["installed"]["client_id"]
        path.write_text(json.dumps(document), encoding="utf-8")
        use_installation_client_file(monkeypatch, path)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)):
        ports = composition.build_google_configuration_operation_ports(
            profile_id=_PROFILE, operation=authority_operation
        )
        with pytest.raises(GoogleConfigurationRefusedError) as prepared:
            ports.prepare_consent()
        with pytest.raises(GoogleConfigurationRefusedError) as signed_in:
            ports.run(
                contracts.GoogleLoginRequest(profile_id=_PROFILE),
                commit=forbidden_commit,
                before_handoff=forbidden_handoff,
                acknowledged=forbidden_handoff,
                terminal_admission=lambda: None,
            )
        assert prepared.value.projection == signed_in.value.projection
        refusal = prepared.value.projection
        assert refusal.provider_code == "REFUSED_GOOGLE_CLIENT_METADATA_UNAVAILABLE"
        assert refusal.message_key == message_key
        assert refusal.verdict is not None
        verdict = refusal.verdict.to_verdict()
        assert verdict.failed_condition_id == "google.auth.client_metadata.available"
        assert dict(verdict.evidence[0].values) == facts
        assert SYNTHETIC_CLIENT_CREDENTIAL not in refusal.model_dump_json()
        original = google_configuration_refusal_error(
            refusal,
            operation_id="a" * 64,
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.REFUSED,
            refusal_code="REFUSED_GOOGLE_CONFIGURATION",
        )
        assert type(original) is GoogleAuthClientMetadataUnavailableError
        assert original.code.code == "REFUSED_GOOGLE_CLIENT_METADATA_UNAVAILABLE"
        assert original.translated_message == message_key
        assert original.context is not None
        assert original.context["operation_id"] == "a" * 64 and original.context["effect"] == "none"
        assert load_token(str(_PROFILE)) is None and load_metadata(str(_PROFILE)) is None


def _consented(profile: str) -> tuple[OAuthToken, OAuthMetadata]:
    """Records a completed browser consent would hand back; the browser itself cannot run here."""
    return (
        OAuthToken(refresh_token=_REFRESH_CREDENTIAL, client_id=SYNTHETIC_CLIENT_ID, token_uri=_OAUTH_ENDPOINT),
        OAuthMetadata(
            account_email="synthetic@example.invalid", granted_scopes=REQUIRED_SCOPES, issued_at=datetime.now(UTC)
        ),
    )


def test_sign_in_creates_the_root_folder_before_anything_is_stored(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Order of effects: consent, folder creation under an admitted write handoff, then the three records."""
    use_installation_client(monkeypatch, tmp_path / "installation")
    events: list[str] = []

    def consent(client: object, profile: str, **_kwargs: object) -> tuple[OAuthToken, OAuthMetadata]:
        events.append("consent")
        return _consented(profile)

    def create_folder(credentials: object, *, profile: str) -> str:
        assert isinstance(credentials, OAuthCredentials)
        assert credentials.client_id == SYNTHETIC_CLIENT_ID and credentials.refresh_token == _REFRESH_CREDENTIAL
        assert load_token(profile) is None and load_metadata(profile) is None and load_drive_config(profile) is None
        events.append("create-folder")
        return "created-root-folder"

    monkeypatch.setattr(composition, "run_login_flow", consent)
    monkeypatch.setattr(composition, "ensure_profile_root_folder", create_folder)

    def commit[T](save: Callable[[], T], *, changed: Callable[[T], bool]) -> T:
        result = save()
        events.append("commit")
        return result

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)):
        ports = composition.build_google_configuration_operation_ports(
            profile_id=_PROFILE, operation=authority_operation
        )
        signed_in = ports.run(
            contracts.GoogleLoginRequest(profile_id=_PROFILE),
            commit=commit,
            before_handoff=lambda action, *, writes=False: events.append(f"before:{action}:{writes}"),
            acknowledged=lambda action, *, writes=False: events.append(f"done:{action}:{writes}"),
            terminal_admission=lambda: None,
        )

        assert isinstance(signed_in, contracts.GoogleLoginProjection)
        assert signed_in.root_folder_id == "created-root-folder"
        assert signed_in.account_email == "synthetic@example.invalid"
        assert events == [
            "consent",
            "before:drive.root-folder.ensure:True",
            "create-folder",
            "done:drive.root-folder.ensure:True",
            "commit",
            "commit",
            "commit",
        ]
        assert load_drive_config(str(_PROFILE)) == DriveConfig(root_folder_id="created-root-folder")
        stored = load_token(str(_PROFILE))
        assert stored is not None and stored.client_id == SYNTHETIC_CLIENT_ID
        assert load_metadata(str(_PROFILE)) is not None


def test_a_sign_in_whose_folder_cannot_be_created_stores_nothing(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_installation_client(monkeypatch, tmp_path / "installation")

    def refuse_folder(credentials: object, *, profile: str) -> str:
        raise OutboundStorageConflictError(
            "folder exists but is not marked as app-owned",
            translated_message="errors.refused.refused_outbound_storage_conflict",
        )

    monkeypatch.setattr(composition, "run_login_flow", lambda client, profile, **_kwargs: _consented(profile))
    monkeypatch.setattr(composition, "ensure_profile_root_folder", refuse_folder)

    def forbidden_commit[T](save: Callable[[], T], *, changed: Callable[[T], bool]) -> T:
        pytest.fail("a sign-in without a root folder reached a save")

    acknowledged: list[str] = []
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)):
        ports = composition.build_google_configuration_operation_ports(
            profile_id=_PROFILE, operation=authority_operation
        )
        with pytest.raises(GoogleConfigurationRefusedError) as refused:
            ports.run(
                contracts.GoogleLoginRequest(profile_id=_PROFILE),
                commit=forbidden_commit,
                before_handoff=lambda action, *, writes=False: None,
                acknowledged=lambda action, *, writes=False: acknowledged.append(action),
                terminal_admission=lambda: None,
            )

        assert refused.value.projection.provider_code == "REFUSED_OUTBOUND_STORAGE_CONFLICT"
        assert acknowledged == []
        assert load_token(str(_PROFILE)) is None
        assert load_metadata(str(_PROFILE)) is None
        assert load_drive_config(str(_PROFILE)) is None
