"""Tests for the storage provider factory.

The factory is the public construction surface for outbound storage, so
these tests exercise the real settings and active-profile flows without
mutating imports, environment variables, or provider behavior through pytest helpers.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from .....core.config import override_settings
from .....core.errors.error_codes import resolve_error_message
from .....core.google_credential_source import GoogleCredentialSourceKind
from .....core.i18n import tr
from .....core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from .....tests.env_scope import scoped_env_var
from .....tests.secure_sql import isolated_runtime_profile
from ...google.impersonation import (
    GoogleAuthAdcUnavailableError,
    GoogleCredentialSourceSelection,
    GoogleImpersonationConfig,
)
from ...google.records import DriveConfig, OAuthClient
from ...google.session_store import save_client, save_credential_source_selection, save_drive_config
from ..errors import OutboundStorageValidationError
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
    probe = subprocess.run(  # noqa: S603 - fixed interpreter argv with in-test script.
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
        override_settings(
            cadrumo_storage_provider_kind=ProviderKind.GOOGLE_DRIVE.value,
            cadrumo_google_drive_root_folder_id="",
        ) as settings,
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


def test_drive_root_whitespace_override_uses_persisted_profile_configuration(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="609a333e-f1cd-4f0e-a2d8-39f0d76e233d") as profile:
        save_drive_config(profile.bucket_id, DriveConfig(root_folder_id="persisted-drive-root"))

        with override_settings(cadrumo_google_drive_root_folder_id="   ") as settings:
            root_folder_id = resolve_drive_root_folder_id(profile=profile.bucket_id, settings=settings)

    assert root_folder_id == "persisted-drive-root"


def test_factory_rejects_google_drive_without_registered_client(tmp_path: Path) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="2e31b7b3-12da-4ae7-abf1-d1fe71bd81d4"),
        override_settings(
            cadrumo_storage_provider_kind=ProviderKind.GOOGLE_DRIVE.value,
            cadrumo_google_drive_root_folder_id="drive-root",
        ) as settings,
        pytest.raises(OutboundStorageValidationError) as raised,
    ):
        get_storage_provider(settings=settings)

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage._factory.errors.google_client_missing"
    assert exc.context == {"profile": "2e31b7b3-12da-4ae7-abf1-d1fe71bd81d4"}
    _assert_factory_verdict(
        exc,
        "storage.factory.google_oauth_client.present",
        {"backend": "google_drive", "field": "google_oauth_client", "valid": False},
    )


def test_factory_rejects_google_drive_without_persisted_token(tmp_path: Path) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="893af7b9-9656-466c-9d8a-5d638b189a20"),
        override_settings(
            cadrumo_storage_provider_kind=ProviderKind.GOOGLE_DRIVE.value,
            cadrumo_google_drive_root_folder_id="drive-root",
        ) as settings,
        pytest.raises(OutboundStorageValidationError) as raised,
    ):
        save_client(
            "893af7b9-9656-466c-9d8a-5d638b189a20",
            OAuthClient(
                client_id="desktop-client.apps.googleusercontent.com",
                client_secret="client-secret",
                project_id="desktop-project",
                auth_uri="https://accounts.google.com/o/oauth2/auth",
                token_uri="https://oauth2.googleapis.com/token",
                auth_provider_x509_cert_url="https://www.googleapis.com/oauth2/v1/certs",
                redirect_uris=("http://localhost",),
            ),
        )
        get_storage_provider(settings=settings)

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage._factory.errors.google_token_missing"
    assert exc.context == {"profile": "893af7b9-9656-466c-9d8a-5d638b189a20"}
    _assert_factory_verdict(
        exc,
        "storage.factory.google_oauth_token.present",
        {"backend": "google_drive", "field": "google_oauth_token", "valid": False},
    )


# ---------------------------------------------------------------------------
# build_google_credentials — GoogleCredentialSourceKind dispatch (#591 slice)
# ---------------------------------------------------------------------------

_TARGET_PRINCIPAL = "aeat-export@example-project.iam.gserviceaccount.com"


def test_build_google_credentials_with_no_persisted_selection_defaults_to_oauth(tmp_path: Path) -> None:
    """A profile that never opted into impersonation gets the pre-existing OAuth-Desktop behaviour.

    Proves the dispatch preserves the default path byte-for-byte: no
    persisted `GoogleCredentialSourceSelection` still resolves through
    `_build_oauth_desktop_credentials`, so the existing
    `google_client_missing` refusal (unchanged translated_message and
    context) still fires when no OAuth client is registered.
    """
    profile = "21a18385-cc88-40ff-a877-43072fa35ca9"
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="21a18385-cc88-40ff-a877-43072fa35ca9"),
        pytest.raises(OutboundStorageValidationError) as raised,
    ):
        build_google_credentials(profile=profile)

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage._factory.errors.google_client_missing"
    assert exc.context == {"profile": profile}


def test_build_google_credentials_with_oauth_desktop_selection_uses_oauth_path(tmp_path: Path) -> None:
    """An explicitly-persisted OAUTH_DESKTOP selection also dispatches to the OAuth path."""
    profile = "5ebf687e-3e08-46f4-b7b1-732ca5bc80be"
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="5ebf687e-3e08-46f4-b7b1-732ca5bc80be"),
        pytest.raises(OutboundStorageValidationError) as raised,
    ):
        save_credential_source_selection(profile, GoogleCredentialSourceSelection())
        build_google_credentials(profile=profile)

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage._factory.errors.google_client_missing"


def test_build_google_credentials_with_impersonation_selection_dispatches_to_impersonation_path(
    tmp_path: Path,
) -> None:
    """A persisted SERVICE_ACCOUNT_IMPERSONATION selection reaches the real impersonation resolver.

    Proves genuine dispatch: pointing
    `GOOGLE_APPLICATION_CREDENTIALS` at a nonexistent path makes the real,
    `google.auth.default()` call inside
    `resolve_impersonated_credentials` raise `GoogleAuthAdcUnavailableError`
    naming the persisted `target_principal` — a failure mode that could
    only be reached if the factory actually dispatched to the
    impersonation resolver rather than the OAuth-Desktop path (which would
    instead raise `google_client_missing`).
    """
    profile = "ee1d3218-58c9-40d2-bfbd-5050a82ee092"
    selection = GoogleCredentialSourceSelection(
        kind=GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION,
        impersonation=GoogleImpersonationConfig(target_principal=_TARGET_PRINCIPAL),
    )

    with (
        scoped_env_var("GOOGLE_APPLICATION_CREDENTIALS", "/nonexistent/path/does-not-exist.json"),
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="ee1d3218-58c9-40d2-bfbd-5050a82ee092"),
        pytest.raises(GoogleAuthAdcUnavailableError) as raised,
    ):
        save_credential_source_selection(profile, selection)
        build_google_credentials(profile=profile)

    assert raised.value.context == {"target_principal": _TARGET_PRINCIPAL}


def test_get_storage_provider_google_drive_dispatches_impersonation_selection_through_full_factory(
    tmp_path: Path,
) -> None:
    """The end-to-end `get_storage_provider` path (not just `build_google_credentials`) dispatches correctly.

    Confirms `get_storage_provider` -> `build_google_credentials` -> the
    impersonation resolver chain holds for the full public entry point
    real CLI/application callers use, not only the narrower unit under
    test above.
    """
    profile = "f09cea6b-e8d3-458e-be9a-9db795214fe2"
    selection = GoogleCredentialSourceSelection(
        kind=GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION,
        impersonation=GoogleImpersonationConfig(target_principal=_TARGET_PRINCIPAL),
    )

    with (
        scoped_env_var("GOOGLE_APPLICATION_CREDENTIALS", "/nonexistent/path/does-not-exist.json"),
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="f09cea6b-e8d3-458e-be9a-9db795214fe2"),
        override_settings(
            cadrumo_storage_provider_kind=ProviderKind.GOOGLE_DRIVE.value,
            cadrumo_google_drive_root_folder_id="drive-root",
        ) as settings,
        pytest.raises(GoogleAuthAdcUnavailableError) as raised,
    ):
        save_credential_source_selection(profile, selection)
        get_storage_provider(settings=settings)

    assert raised.value.context == {"target_principal": _TARGET_PRINCIPAL}
