"""Tests for `get_storage_provider`."""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.adapters.outbound.storage import (
    ProviderKind,
    StorageValidationError,
    get_storage_provider,
)
from aeat.adapters.outbound.storage._google_drive import GoogleDriveProvider
from aeat.adapters.outbound.storage._local import LocalFileSystemProvider
from aeat.adapters.outbound.storage._testing import InMemoryDriveProvider
from aeat.core.config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def _settings(**overrides: object) -> Settings:
    return Settings().model_copy(update=overrides)


def _patch_profile(monkeypatch: pytest.MonkeyPatch, name: str = "primary") -> None:
    monkeypatch.setattr(
        "aeat.adapters.outbound.storage._factory._resolve_profile",
        lambda override: (override or "").strip() or name,
    )


def test_get_storage_provider_returns_in_memory_for_in_memory_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    # in_memory does not require a profile, so no profile patch needed.
    provider = get_storage_provider(settings=_settings(aeat_storage_provider_kind="in_memory"))
    assert isinstance(provider, InMemoryDriveProvider)


def test_get_storage_provider_returns_local_filesystem_for_local_kind(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_profile(monkeypatch, "primary")
    provider = get_storage_provider(
        settings=_settings(
            aeat_storage_provider_kind="local_filesystem",
            aeat_local_storage_root=tmp_path / "storage",
        ),
    )
    assert isinstance(provider, LocalFileSystemProvider)
    assert provider.root == tmp_path / "storage" / "primary"


def test_get_storage_provider_threads_profile_override_into_local_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_profile(monkeypatch, "primary")
    provider = get_storage_provider(
        profile_override="business",
        settings=_settings(
            aeat_storage_provider_kind="local_filesystem",
            aeat_local_storage_root=tmp_path / "storage",
        ),
    )
    assert isinstance(provider, LocalFileSystemProvider)
    assert provider.root == tmp_path / "storage" / "business"


def test_get_storage_provider_refuses_unknown_kind() -> None:
    with pytest.raises(StorageValidationError, match="not a recognised ProviderKind"):
        get_storage_provider(settings=_settings(aeat_storage_provider_kind="onedrive"))


def test_get_storage_provider_refuses_empty_kind() -> None:
    with pytest.raises(StorageValidationError, match="is empty"):
        get_storage_provider(settings=_settings(aeat_storage_provider_kind="   "))


def test_get_storage_provider_refuses_drive_without_root_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_profile(monkeypatch, "primary")
    with pytest.raises(StorageValidationError, match="aeat_google_drive_root_folder_id"):
        get_storage_provider(
            settings=_settings(
                aeat_storage_provider_kind="google_drive",
                aeat_google_drive_root_folder_id=None,
            ),
        )


def test_get_storage_provider_drive_refuses_when_no_oauth_client_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_profile(monkeypatch, "primary")
    monkeypatch.setattr("aeat.adapters.outbound.google._session_store.load_client", lambda profile: None)
    with pytest.raises(StorageValidationError, match="no Google OAuth client registered"):
        get_storage_provider(
            settings=_settings(
                aeat_storage_provider_kind="google_drive",
                aeat_google_drive_root_folder_id="root-folder-id-xyz",
            ),
        )


def test_get_storage_provider_drive_refuses_when_no_oauth_token_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_profile(monkeypatch, "primary")
    from aeat.adapters.outbound.google._records import OAuthClient

    sample_client = OAuthClient(
        client_id="abc.apps.googleusercontent.com",
        client_secret="GOCSPX-fake",
        project_id="test-project",
        auth_uri="https://accounts.google.com/o/oauth2/auth",
        token_uri="https://oauth2.googleapis.com/token",
        auth_provider_x509_cert_url="https://www.googleapis.com/oauth2/v1/certs",
        redirect_uris=("http://localhost",),
    )
    monkeypatch.setattr("aeat.adapters.outbound.google._session_store.load_client", lambda profile: sample_client)
    monkeypatch.setattr("aeat.adapters.outbound.google._session_store.load_token", lambda profile: None)
    with pytest.raises(StorageValidationError, match="no Google OAuth token persisted"):
        get_storage_provider(
            settings=_settings(
                aeat_storage_provider_kind="google_drive",
                aeat_google_drive_root_folder_id="root-folder-id-xyz",
            ),
        )


def test_get_storage_provider_returns_drive_provider_when_records_present(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_profile(monkeypatch, "primary")
    from aeat.adapters.outbound.google._records import OAuthClient, OAuthToken

    sample_client = OAuthClient(
        client_id="abc.apps.googleusercontent.com",
        client_secret="GOCSPX-fake",
        project_id="test-project",
        auth_uri="https://accounts.google.com/o/oauth2/auth",
        token_uri="https://oauth2.googleapis.com/token",
        auth_provider_x509_cert_url="https://www.googleapis.com/oauth2/v1/certs",
        redirect_uris=("http://localhost",),
    )
    sample_token = OAuthToken(refresh_token="1//refresh", token_uri="https://oauth2.googleapis.com/token")
    monkeypatch.setattr("aeat.adapters.outbound.google._session_store.load_client", lambda profile: sample_client)
    monkeypatch.setattr("aeat.adapters.outbound.google._session_store.load_token", lambda profile: sample_token)

    provider = get_storage_provider(
        settings=_settings(
            aeat_storage_provider_kind="google_drive",
            aeat_google_drive_root_folder_id="root-folder-id-xyz",
        ),
    )
    assert isinstance(provider, GoogleDriveProvider)
    assert provider.root_folder_id == "root-folder-id-xyz"


def test_parse_kind_accepts_every_canonical_value() -> None:
    from aeat.adapters.outbound.storage._factory import _parse_kind

    for kind in ProviderKind:
        assert _parse_kind(kind.value) is kind


def test_parse_kind_is_case_insensitive() -> None:
    from aeat.adapters.outbound.storage._factory import _parse_kind

    assert _parse_kind("LOCAL_FILESYSTEM") is ProviderKind.LOCAL_FILESYSTEM
    assert _parse_kind("Google_Drive") is ProviderKind.GOOGLE_DRIVE


def test_get_storage_provider_resolves_default_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No settings passed → load_settings() default → local_filesystem backend."""

    _patch_profile(monkeypatch, "primary")
    monkeypatch.setattr(
        "aeat.adapters.outbound.storage._factory.load_settings",
        lambda: _settings(
            aeat_storage_provider_kind="local_filesystem",
            aeat_local_storage_root=tmp_path / "storage",
        ),
    )
    provider = get_storage_provider()
    assert isinstance(provider, LocalFileSystemProvider)
