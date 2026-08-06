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

from .....core import GoogleCredentialSourceKind
from .....core.config import override_settings
from .....core.errors import resolve_error_message
from .....core.i18n import tr
from .....tests.env_scope import scoped_env_var
from .....tests.secure_sql import isolated_runtime_profile
from ...google import (
    DriveConfig,
    GoogleAuthAdcUnavailableError,
    GoogleCredentialSourceSelection,
    GoogleImpersonationConfig,
    OAuthClient,
    save_client,
    save_credential_source_selection,
    save_drive_config,
)
from .. import (
    OutboundStorageValidationError,
    ProviderKind,
    StorageProvider,
    build_google_credentials,
    get_storage_provider,
    resolve_drive_root_folder_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


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

                import cadrumo.adapters.outbound.storage._factory

                watched = (
                    "cadrumo.adapters.outbound.storage._google_drive",
                    "cadrumo.adapters.outbound.storage._local",
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
        "cadrumo.adapters.outbound.storage._local": False,
    }


def test_get_storage_provider_local_uses_active_profile_bucket_root(tmp_path: Path) -> None:
    payload = b"factory payload"
    object_key_hmac = "a" * 64

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="factory-local") as profile:
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
    assert exc.translated_message == "adapters.outbound.storage.factory.errors.kind_empty"
    assert exc.context == {"value": "   "}
    assert resolve_error_message(exc) == tr(exc.translated_message, **(exc.context or {}))


def test_factory_rejects_unknown_provider_kind_with_localized_context() -> None:
    with (
        override_settings(cadrumo_storage_provider_kind="not-a-provider") as settings,
        pytest.raises(OutboundStorageValidationError) as raised,
    ):
        get_storage_provider(settings=settings)

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage.factory.errors.kind_unknown"
    assert exc.context == {
        "value": "not-a-provider",
        "expected": "google_drive, local_filesystem",
    }
    assert resolve_error_message(exc) == tr(exc.translated_message, **(exc.context or {}))


def test_factory_rejects_google_drive_without_root_before_loading_credentials(tmp_path: Path) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="factory-drive-missing-root"),
        override_settings(
            cadrumo_storage_provider_kind=ProviderKind.GOOGLE_DRIVE.value,
            cadrumo_google_drive_root_folder_id="",
        ) as settings,
        pytest.raises(OutboundStorageValidationError) as raised,
    ):
        get_storage_provider(settings=settings)

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage.factory.errors.drive_root_missing"
    assert exc.context == {"profile": "factory-drive-missing-root"}
    assert exc.suggestion == "aeat config google folder set <id>"


def test_drive_root_whitespace_override_uses_persisted_profile_configuration(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="factory-drive-persisted-root") as profile:
        save_drive_config(profile.bucket_id, DriveConfig(root_folder_id="persisted-drive-root"))

        with override_settings(cadrumo_google_drive_root_folder_id="   ") as settings:
            root_folder_id = resolve_drive_root_folder_id(profile=profile.bucket_id, settings=settings)

    assert root_folder_id == "persisted-drive-root"


def test_factory_rejects_google_drive_without_registered_client(tmp_path: Path) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="factory-drive-missing-client"),
        override_settings(
            cadrumo_storage_provider_kind=ProviderKind.GOOGLE_DRIVE.value,
            cadrumo_google_drive_root_folder_id="drive-root",
        ) as settings,
        pytest.raises(OutboundStorageValidationError) as raised,
    ):
        get_storage_provider(settings=settings)

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage.factory.errors.google_client_missing"
    assert exc.context == {"profile": "factory-drive-missing-client"}
    assert exc.suggestion == "aeat config google register --client-json <path>"


def test_factory_rejects_google_drive_without_persisted_token(tmp_path: Path) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="factory-drive-missing-token"),
        override_settings(
            cadrumo_storage_provider_kind=ProviderKind.GOOGLE_DRIVE.value,
            cadrumo_google_drive_root_folder_id="drive-root",
        ) as settings,
        pytest.raises(OutboundStorageValidationError) as raised,
    ):
        save_client(
            "factory-drive-missing-token",
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
    assert exc.translated_message == "adapters.outbound.storage.factory.errors.google_token_missing"
    assert exc.context == {"profile": "factory-drive-missing-token"}
    assert exc.suggestion == "aeat config google login"


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
    profile = "factory-dispatch-default-oauth"
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="factory-dispatch-default-oauth"),
        pytest.raises(OutboundStorageValidationError) as raised,
    ):
        build_google_credentials(profile=profile)

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage.factory.errors.google_client_missing"
    assert exc.context == {"profile": profile}


def test_build_google_credentials_with_oauth_desktop_selection_uses_oauth_path(tmp_path: Path) -> None:
    """An explicitly-persisted OAUTH_DESKTOP selection also dispatches to the OAuth path."""
    profile = "factory-dispatch-explicit-oauth"
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="factory-dispatch-explicit-oauth"),
        pytest.raises(OutboundStorageValidationError) as raised,
    ):
        save_credential_source_selection(profile, GoogleCredentialSourceSelection())
        build_google_credentials(profile=profile)

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage.factory.errors.google_client_missing"


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
    profile = "factory-dispatch-impersonation"
    selection = GoogleCredentialSourceSelection(
        kind=GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION,
        impersonation=GoogleImpersonationConfig(target_principal=_TARGET_PRINCIPAL),
    )

    with (
        scoped_env_var("GOOGLE_APPLICATION_CREDENTIALS", "/nonexistent/path/does-not-exist.json"),
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="factory-dispatch-impersonation"),
        pytest.raises(GoogleAuthAdcUnavailableError) as raised,
    ):
        save_credential_source_selection(profile, selection)
        build_google_credentials(profile=profile)

    assert raised.value.context == {"target_principal": _TARGET_PRINCIPAL}
    assert raised.value.suggestion == "gcloud auth application-default login"


def test_get_storage_provider_google_drive_dispatches_impersonation_selection_through_full_factory(
    tmp_path: Path,
) -> None:
    """The end-to-end `get_storage_provider` path (not just `build_google_credentials`) dispatches correctly.

    Confirms `get_storage_provider` -> `build_google_credentials` -> the
    impersonation resolver chain holds for the full public entry point
    real CLI/application callers use, not only the narrower unit under
    test above.
    """
    profile = "factory-full-dispatch-impersonation"
    selection = GoogleCredentialSourceSelection(
        kind=GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION,
        impersonation=GoogleImpersonationConfig(target_principal=_TARGET_PRINCIPAL),
    )

    with (
        scoped_env_var("GOOGLE_APPLICATION_CREDENTIALS", "/nonexistent/path/does-not-exist.json"),
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="factory-full-dispatch-impersonation"),
        override_settings(
            cadrumo_storage_provider_kind=ProviderKind.GOOGLE_DRIVE.value,
            cadrumo_google_drive_root_folder_id="drive-root",
        ) as settings,
        pytest.raises(GoogleAuthAdcUnavailableError) as raised,
    ):
        save_credential_source_selection(profile, selection)
        get_storage_provider(settings=settings)

    assert raised.value.context == {"target_principal": _TARGET_PRINCIPAL}
