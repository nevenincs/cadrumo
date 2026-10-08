"""Tests for the storage provider factory.

The factory is the public construction surface for outbound storage, so
these tests exercise the real settings and active-profile flows without
mutating imports, environment variables, or provider behavior through pytest helpers.
"""

from __future__ import annotations

import hashlib
import json
import sys
import textwrap
from pathlib import Path

import pytest
from google.oauth2.credentials import Credentials as OAuthCredentials

from .....core.config import override_settings
from .....core.errors.error_codes import resolve_error_message
from .....core.i18n.render import tr
from .....core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from .....tests.audited_process import run_audited_process
from ....persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...google import root_folder
from ...google.errors import GoogleAuthClientMetadataUnavailableError, GoogleAuthSignInRequiredError
from ...google.records import DriveConfig, OAuthToken
from ...google.tests.installation_client_support import (
    SYNTHETIC_CLIENT_CREDENTIAL,
    SYNTHETIC_CLIENT_ID,
    use_absent_installation_client,
    use_installation_client,
)
from ...google.tests.session_records import save_drive_config, save_token
from .._google_drive import GoogleDriveProvider
from ..errors import OutboundStorageConflictError, OutboundStorageValidationError
from ..factory import build_google_credentials, get_storage_provider, resolve_drive_root_folder_id
from ..protocol import StorageProvider
from ..records import ProviderKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _assert_factory_verdict(
    error: OutboundStorageValidationError,
    condition_id: str,
    facts: dict[str, str | bool],
) -> None:
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == condition_id
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.missing_argument_names == ()
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert len(verdict.evidence) == 1
    evidence = verdict.evidence[0]
    assert evidence.condition_id == condition_id
    assert evidence.evidence_id == f"{condition_id}.observation"
    assert evidence.provenance is ActionEvidenceProvenance.APPLICATION_STATE
    assert dict(evidence.values) == facts


def _hash(payload: bytes) -> str:
    return f"sha256-{hashlib.sha256(payload).hexdigest()}"


def test_factory_import_does_not_import_concrete_backends() -> None:
    probe = run_audited_process(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import json
                import sys

                import cadrumo.adapters.outbound.storage.factory

                watched = (
                    "cadrumo.adapters.outbound.storage._google_drive",
                    "cadrumo.adapters.outbound.storage.local",
                )
                print(json.dumps({name: name in sys.modules for name in watched}, sort_keys=True))
                """
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert probe.returncode == 0, probe.stderr
    assert json.loads(probe.stdout) == {
        "cadrumo.adapters.outbound.storage._google_drive": False,
        "cadrumo.adapters.outbound.storage.local": False,
    }


def test_get_storage_provider_local_uses_active_profile_bucket_root(tmp_path: Path) -> None:
    payload = b"factory payload"
    object_key_hmac = "a" * 64

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="38b1affb-eebd-4a49-b6b8-5932de5a8e17") as profile:
        with override_settings(cadrumo_storage_provider_kind=ProviderKind.LOCAL_FILESYSTEM.value):
            provider = get_storage_provider()

        assert isinstance(provider, StorageProvider)
        metadata = provider.put(
            "ledger_transaction",
            object_key_hmac,
            payload,
            content_hash=_hash(payload),
            label="factory",
        )
        fetched, reloaded = provider.get("ledger_transaction", object_key_hmac)

    assert fetched == payload
    assert reloaded == metadata
    assert Path(metadata.provider_object_id).is_relative_to(profile.paths.blobs_dir)


def test_factory_rejects_blank_provider_kind_with_localized_context() -> None:
    with (
        override_settings(cadrumo_storage_provider_kind="   ") as settings,
        pytest.raises(OutboundStorageValidationError) as raised,
    ):
        get_storage_provider(settings=settings)

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage._factory.errors.kind_empty"
    assert exc.context == {"value": "   "}
    _assert_factory_verdict(
        exc,
        "storage.factory.provider_kind.valid",
        {"field": "cadrumo_storage_provider_kind", "valid": False},
    )
    assert resolve_error_message(exc) == tr(exc.translated_message, **(exc.context or {}))


def test_factory_rejects_unknown_provider_kind_with_localized_context() -> None:
    with (
        override_settings(cadrumo_storage_provider_kind="not-a-provider") as settings,
        pytest.raises(OutboundStorageValidationError) as raised,
    ):
        get_storage_provider(settings=settings)

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage._factory.errors.kind_unknown"
    assert exc.context == {
        "value": "not-a-provider",
        "expected": "google_drive, local_filesystem",
    }
    _assert_factory_verdict(
        exc,
        "storage.factory.provider_kind.valid",
        {"field": "cadrumo_storage_provider_kind", "valid": False},
    )
    assert resolve_error_message(exc) == tr(exc.translated_message, **(exc.context or {}))


def test_factory_rejects_google_drive_without_root_before_loading_credentials(tmp_path: Path) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="a5106137-0c0d-4f8f-9c58-606f5bd06dc8"),
        override_settings(cadrumo_storage_provider_kind=ProviderKind.GOOGLE_DRIVE.value) as settings,
        pytest.raises(OutboundStorageValidationError) as raised,
    ):
        get_storage_provider(settings=settings)

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage._factory.errors.drive_root_missing"
    assert exc.context == {"profile": "a5106137-0c0d-4f8f-9c58-606f5bd06dc8"}
    _assert_factory_verdict(
        exc,
        "storage.factory.google_drive_root_folder_id.present",
        {"backend": "google_drive", "field": "google_drive_root_folder_id", "valid": False},
    )


def test_the_drive_root_comes_only_from_the_folder_stored_for_the_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The environment variable that used to supply a folder is not read."""
    monkeypatch.setenv("CADRUMO_GOOGLE_DRIVE_ROOT_FOLDER_ID", "folder-from-the-environment")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="609a333e-f1cd-4f0e-a2d8-39f0d76e233d") as profile:
        assert resolve_drive_root_folder_id(profile=profile.bucket_id) == ""
        save_drive_config(profile.bucket_id, DriveConfig(root_folder_id="created-drive-root"))

        root_folder_id = resolve_drive_root_folder_id(profile=profile.bucket_id)

    assert root_folder_id == "created-drive-root"


def test_factory_refuses_google_drive_when_the_installation_carries_no_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    use_absent_installation_client(monkeypatch, tmp_path)
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="2e31b7b3-12da-4ae7-abf1-d1fe71bd81d4"),
        override_settings(cadrumo_storage_provider_kind=ProviderKind.GOOGLE_DRIVE.value) as settings,
        pytest.raises(GoogleAuthClientMetadataUnavailableError) as raised,
    ):
        save_drive_config("2e31b7b3-12da-4ae7-abf1-d1fe71bd81d4", DriveConfig(root_folder_id="drive-root"))
        get_storage_provider(settings=settings)

    assert raised.value.code.code == "REFUSED_GOOGLE_CLIENT_METADATA_UNAVAILABLE"
    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None and verdict.failed_condition_id == "google.auth.client_metadata.available"


def test_factory_rejects_google_drive_without_persisted_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    use_installation_client(monkeypatch, tmp_path)
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="893af7b9-9656-466c-9d8a-5d638b189a20"),
        override_settings(cadrumo_storage_provider_kind=ProviderKind.GOOGLE_DRIVE.value) as settings,
        pytest.raises(OutboundStorageValidationError) as raised,
    ):
        save_drive_config("893af7b9-9656-466c-9d8a-5d638b189a20", DriveConfig(root_folder_id="drive-root"))
        get_storage_provider(settings=settings)

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage._factory.errors.google_token_missing"
    assert exc.context == {"profile": "893af7b9-9656-466c-9d8a-5d638b189a20"}
    _assert_factory_verdict(
        exc,
        "storage.factory.google_oauth_token.present",
        {"backend": "google_drive", "field": "google_oauth_token", "valid": False},
    )


def test_build_google_credentials_refuses_before_reading_the_token_when_no_client_is_installed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A stored sign-in cannot be used without the installation client it was minted for."""
    profile = "21a18385-cc88-40ff-a877-43072fa35ca9"
    use_absent_installation_client(monkeypatch, tmp_path)
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=profile),
        pytest.raises(GoogleAuthClientMetadataUnavailableError),
    ):
        save_token(
            profile,
            OAuthToken(
                refresh_token="1//refresh-token",
                client_id=SYNTHETIC_CLIENT_ID,
                token_uri="https://oauth2.googleapis.com/token",
            ),
        )
        build_google_credentials(profile=profile)


def test_build_google_credentials_pairs_the_installation_client_with_the_three_non_sensitive_scopes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A stored sign-in is hydrated with the installation client and the consented scope set, nothing wider."""
    profile = "0d3ee1f5-2f0b-4a62-8a56-7d7f7e0a9b11"
    use_installation_client(monkeypatch, tmp_path)
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=profile):
        save_token(
            profile,
            OAuthToken(
                refresh_token="1//refresh-token",
                client_id=SYNTHETIC_CLIENT_ID,
                token_uri="https://oauth2.googleapis.com/token",
            ),
        )
        credentials = build_google_credentials(profile=profile)

    assert isinstance(credentials, OAuthCredentials)
    assert credentials.client_id == SYNTHETIC_CLIENT_ID
    assert credentials.client_secret == SYNTHETIC_CLIENT_CREDENTIAL
    assert credentials.scopes == [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/drive.file",
    ]


def test_build_google_credentials_never_pairs_a_token_with_a_client_that_did_not_mint_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A token minted under another client is refused before any credential object exists."""
    profile = "5f6a1c0e-83f1-4f0e-9a70-2d8f6c4b7e19"
    use_installation_client(monkeypatch, tmp_path)
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=profile),
        pytest.raises(GoogleAuthSignInRequiredError) as raised,
    ):
        save_token(
            profile,
            OAuthToken(
                refresh_token="1//refresh-token",
                client_id="development-client.apps.googleusercontent.com",
                token_uri="https://oauth2.googleapis.com/token",
            ),
        )
        build_google_credentials(profile=profile)

    assert raised.value.code.code == "REFUSED_GOOGLE_SIGN_IN_REQUIRED"
    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None and verdict.failed_condition_id == "google.auth.sign_in_client.bound"


def _signed_in_profile(profile: str) -> None:
    save_drive_config(profile, DriveConfig(root_folder_id="stored-drive-root"))
    save_token(
        profile,
        OAuthToken(
            refresh_token="1//refresh-token",
            client_id=SYNTHETIC_CLIENT_ID,
            token_uri="https://oauth2.googleapis.com/token",
        ),
    )


def test_the_drive_provider_is_built_only_after_the_stored_root_is_read_back_as_ours(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The read-back is its own admitted provider handoff, after credentials and before any use."""
    profile = "0b6d3f7a-2c1e-4a59-8d43-9e7f5a1c6b20"
    use_installation_client(monkeypatch, tmp_path)
    events: list[str] = []

    def read_back(credentials: object, *, root_folder_id: str, profile: str | None) -> None:
        assert profile == "0b6d3f7a-2c1e-4a59-8d43-9e7f5a1c6b20"
        assert isinstance(credentials, OAuthCredentials) and credentials.client_id == SYNTHETIC_CLIENT_ID
        events.append(f"verify:{root_folder_id}")

    monkeypatch.setattr(root_folder, "require_owned_root_folder", read_back)
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=profile),
        override_settings(cadrumo_storage_provider_kind=ProviderKind.GOOGLE_DRIVE.value) as settings,
    ):
        _signed_in_profile(profile)
        provider = get_storage_provider(
            settings=settings,
            before_handoff=lambda action, *, writes=False: events.append(f"before:{action}"),
            acknowledged=lambda action, *, writes=False: events.append(f"done:{action}"),
        )
        direct = get_storage_provider(settings=settings)

    assert events == [
        "before:google.credentials-acquisition",
        "done:google.credentials-acquisition",
        "before:drive.root-folder.verification",
        "verify:stored-drive-root",
        "done:drive.root-folder.verification",
        "verify:stored-drive-root",
    ]
    assert isinstance(provider, GoogleDriveProvider) and provider.root_folder_id == "stored-drive-root"
    assert isinstance(direct, GoogleDriveProvider) and direct.root_folder_id == "stored-drive-root"


def test_a_stored_root_that_is_not_ours_yields_no_drive_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profile = "6c9e2b14-5d7a-4f38-b0a1-3e8d7c5f4a92"
    use_installation_client(monkeypatch, tmp_path)
    events: list[str] = []

    def refuse(credentials: object, *, root_folder_id: str, profile: str | None) -> None:
        assert profile == "6c9e2b14-5d7a-4f38-b0a1-3e8d7c5f4a92"
        raise OutboundStorageConflictError(
            "the stored Drive root is not a live folder created by this application",
            translated_message="adapters.google.root_folder.errors.root_folder_not_owned",
        )

    monkeypatch.setattr(root_folder, "require_owned_root_folder", refuse)
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=profile),
        override_settings(cadrumo_storage_provider_kind=ProviderKind.GOOGLE_DRIVE.value) as settings,
        pytest.raises(OutboundStorageConflictError),
    ):
        _signed_in_profile(profile)
        get_storage_provider(
            settings=settings,
            before_handoff=lambda action, *, writes=False: events.append(f"before:{action}"),
            acknowledged=lambda action, *, writes=False: events.append(f"done:{action}"),
        )

    # The verification handoff was admitted and never acknowledged.
    assert events[-1] == "before:drive.root-folder.verification"
