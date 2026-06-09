"""Tests for the storage provider factory.

The factory is the public construction surface for outbound storage, so
these tests exercise the real settings and active-profile flows without
patching imports, environment variables, or provider behavior.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from .....core.config import override_settings
from .....core.errors import resolve_error_message
from .....core.i18n import tr
from .....tests.secure_sql import isolated_runtime_profile
from ...google._records import OAuthClient
from ...google._session_store import save_client
from .. import OutboundStorageValidationError, ProviderKind, StorageProvider, get_storage_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _hash(payload: bytes) -> str:
    return f"sha256-{hashlib.sha256(payload).hexdigest()}"


def test_factory_import_does_not_import_concrete_backends() -> None:
    tree = ast.parse((Path(__file__).parent.parent / "_factory.py").read_text(encoding="utf-8"))
    concrete_backend_modules = {
        "aeat.adapters.outbound.storage._google_drive",
        "aeat.adapters.outbound.storage._local",
        "._google_drive",
        "._local",
    }
    top_level_imports = {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module in concrete_backend_modules
    }

    assert top_level_imports == set()


def test_get_storage_provider_local_uses_active_profile_bucket_root(tmp_path: Path) -> None:
    payload = b"factory payload"
    object_key_hmac = "a" * 64

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="factory-local") as profile:
        with override_settings(aeat_storage_provider_kind=ProviderKind.LOCAL_FILESYSTEM.value):
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
        override_settings(aeat_storage_provider_kind="   ") as settings,
        pytest.raises(OutboundStorageValidationError) as raised,
    ):
        get_storage_provider(settings=settings)

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage.factory.errors.kind_empty"
    assert exc.context == {"value": "   "}
    assert resolve_error_message(exc) == tr(exc.translated_message, **(exc.context or {}))


def test_factory_rejects_unknown_provider_kind_with_localized_context() -> None:
    with (
        override_settings(aeat_storage_provider_kind="not-a-provider") as settings,
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
            aeat_storage_provider_kind=ProviderKind.GOOGLE_DRIVE.value,
            aeat_google_drive_root_folder_id="",
        ) as settings,
        pytest.raises(OutboundStorageValidationError) as raised,
    ):
        get_storage_provider(settings=settings)

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage.factory.errors.drive_root_missing"
    assert exc.context == {"profile": "factory-drive-missing-root"}
    assert exc.suggestion == "aeat config google folder set <id>"


def test_factory_rejects_google_drive_without_registered_client(tmp_path: Path) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="factory-drive-missing-client"),
        override_settings(
            aeat_storage_provider_kind=ProviderKind.GOOGLE_DRIVE.value,
            aeat_google_drive_root_folder_id="drive-root",
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
            aeat_storage_provider_kind=ProviderKind.GOOGLE_DRIVE.value,
            aeat_google_drive_root_folder_id="drive-root",
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
