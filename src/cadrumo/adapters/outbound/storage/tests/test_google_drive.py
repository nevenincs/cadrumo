"""Unit coverage for Google Drive storage provider boundaries.

These tests cover refusal paths that happen before a Drive service is
constructed. They use no Drive API doubles or patched dependencies.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from typing import Any
from urllib.parse import parse_qs

import pytest

from .....core.errors import resolve_error_message
from .....core.i18n import tr
from ...google.tests._drive_media_server import drive_files_list_endpoint
from .. import OutboundStorageIntegrityError, OutboundStorageNetworkError, OutboundStorageValidationError
from .._google_drive import GoogleDriveProvider, _drive_storage_content_hash

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _provider() -> GoogleDriveProvider:
    return GoogleDriveProvider(credentials=object(), root_folder_id="drive-root", vault_folder_name="cadrumo-vault")


def test_google_drive_explicit_constructor_does_not_build_google_client() -> None:
    probe = subprocess.run(  # noqa: S603 - fixed interpreter argv with in-test script.
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import json
                import sys

                from cadrumo.adapters.outbound.storage._google_drive import GoogleDriveProvider

                provider = GoogleDriveProvider(
                    credentials=object(),
                    root_folder_id="drive-root",
                    vault_folder_name="cadrumo-vault",
                )
                watched = (
                    "googleapiclient.discovery",
                    "googleapiclient.http",
                )
                print(json.dumps({"root_folder_id": provider.root_folder_id, **{name: name in sys.modules for name in watched}}, sort_keys=True))
                """
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert probe.returncode == 0, probe.stderr
    assert json.loads(probe.stdout) == {
        "googleapiclient.discovery": False,
        "googleapiclient.http": False,
        "root_folder_id": "drive-root",
    }


@pytest.mark.parametrize(
    ("provider_kwargs", "message", "context"),
    (
        (
            {"credentials": object(), "root_folder_id": " ", "vault_folder_name": "cadrumo-vault"},
            "adapters.outbound.storage.google_drive.errors.root_folder_id_blank",
            {"root_folder_id": " "},
        ),
        (
            {"credentials": object(), "root_folder_id": "drive-root", "vault_folder_name": " "},
            "adapters.outbound.storage.google_drive.errors.vault_folder_name_blank",
            None,
        ),
    ),
    ids=("blank-root-folder", "blank-vault-folder"),
)
def test_google_drive_provider_rejects_blank_constructor_values_with_localized_message(
    provider_kwargs: dict[str, object],
    message: str,
    context: dict[str, str] | None,
) -> None:
    with pytest.raises(OutboundStorageValidationError) as raised:
        kwargs: Any = provider_kwargs
        GoogleDriveProvider(**kwargs)

    exc = raised.value
    assert exc.translated_message == message
    assert exc.translated_message is not None
    assert exc.context == context
    assert resolve_error_message(exc) == tr(exc.translated_message, **(exc.context or {}))


def test_google_drive_provider_refuses_the_former_product_vault_before_service_construction() -> None:
    """The legacy Drive folder is never adopted as Cadrumo state."""
    with pytest.raises(OutboundStorageValidationError) as raised:
        GoogleDriveProvider(credentials=object(), root_folder_id="drive-root", vault_folder_name="aeat-vault")

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage.google_drive.errors.former_vault_folder"
    assert exc.context == {"vault_folder_name": "aeat-vault"}
    assert exc.context is not None
    assert resolve_error_message(exc) == tr(exc.translated_message, **exc.context)


def test_google_drive_read_metadata_requires_the_same_typed_app_properties_contract() -> None:
    with pytest.raises(OutboundStorageIntegrityError, match="appProperties"):
        _drive_storage_content_hash({"id": "drive-file", "appProperties": {"content_hash": "sha256-x"}})


def test_vault_resolution_follows_page_token_to_an_owned_folder() -> None:
    """A generated Drive client reaches an owned vault folder on page two."""
    with drive_files_list_endpoint(
        pages=(
            {"files": [], "nextPageToken": "vault-page-two"},
            {
                "files": [
                    {
                        "id": "vault-id",
                        "name": "cadrumo-vault",
                        "mimeType": "application/vnd.google-apps.folder",
                        "appProperties": {"cadrumo_vault_app": "cadrumo"},
                    }
                ]
            },
        )
    ) as endpoint:
        provider = _provider()
        provider._service = endpoint.service

        assert provider._resolve_vault_folder() == "vault-id"

    assert len(endpoint.requested_queries) == 2
    assert parse_qs(endpoint.requested_queries[1])["pageToken"] == ["vault-page-two"]


def test_namespace_resolution_follows_page_token_to_an_owned_folder() -> None:
    """A generated Drive client reaches an owned namespace folder on page two."""
    with drive_files_list_endpoint(
        pages=(
            {
                "files": [
                    {
                        "id": "vault-id",
                        "name": "cadrumo-vault",
                        "mimeType": "application/vnd.google-apps.folder",
                        "appProperties": {"cadrumo_vault_app": "cadrumo"},
                    }
                ]
            },
            {"files": [], "nextPageToken": "namespace-page-two"},
            {
                "files": [
                    {
                        "id": "namespace-id",
                        "name": "ledger_transaction",
                        "appProperties": {"cadrumo_vault_app": "cadrumo"},
                    }
                ]
            },
        )
    ) as endpoint:
        provider = _provider()
        provider._service = endpoint.service

        assert provider._resolve_namespace_folder("ledger_transaction", create=False) == "namespace-id"

    assert len(endpoint.requested_queries) == 3
    assert parse_qs(endpoint.requested_queries[2])["pageToken"] == ["namespace-page-two"]


def test_file_resolution_follows_page_token_to_a_matching_owned_object() -> None:
    """A generated Drive client reaches the full-HMAC match on page two."""
    object_key_hmac = "a" * 64
    with drive_files_list_endpoint(
        pages=(
            {"files": [], "nextPageToken": "object-page-two"},
            {
                "files": [
                    {
                        "id": "object-id",
                        "name": "aaaaaaaa--payload.bin",
                        "appProperties": {
                            "cadrumo_vault_app": "cadrumo",
                            "object_key_hmac": object_key_hmac,
                        },
                    }
                ]
            },
        )
    ) as endpoint:
        provider = _provider()
        provider._service = endpoint.service

        entry = provider._find_file("namespace-id", object_key_hmac)

    assert entry is not None
    assert entry["id"] == "object-id"
    assert len(endpoint.requested_queries) == 2
    assert parse_qs(endpoint.requested_queries[1])["pageToken"] == ["object-page-two"]


@pytest.mark.parametrize(
    ("put_kwargs", "message"),
    (
        (
            {"namespace": "", "object_key_hmac": "a" * 64, "payload": b"x", "content_hash": "sha256-x", "label": "x"},
            "adapters.outbound.storage.google_drive.errors.namespace_blank",
        ),
        (
            {
                "namespace": "ledger_transaction",
                "object_key_hmac": " ",
                "payload": b"x",
                "content_hash": "sha256-x",
                "label": "x",
            },
            "adapters.outbound.storage.google_drive.errors.object_key_hmac_blank",
        ),
        (
            {
                "namespace": "ledger_transaction",
                "object_key_hmac": "a" * 64,
                "payload": b"x",
                "content_hash": " ",
                "label": "x",
            },
            "adapters.outbound.storage.google_drive.errors.content_hash_blank",
        ),
    ),
    ids=("blank-namespace", "blank-object-hmac", "blank-content-hash"),
)
def test_google_drive_provider_rejects_blank_put_values_before_service_construction(
    put_kwargs: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(OutboundStorageValidationError) as raised:
        kwargs: Any = put_kwargs
        _provider().put(**kwargs)

    exc = raised.value
    assert exc.translated_message == message
    assert exc.translated_message is not None
    assert resolve_error_message(exc) == tr(exc.translated_message, **(exc.context or {}))


def test_google_drive_provider_rejects_forbidden_namespace_before_service_construction() -> None:
    with pytest.raises(OutboundStorageValidationError) as raised:
        _provider().put("with/slash", "a" * 64, b"x", content_hash="sha256-x", label="x")

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage.google_drive.errors.namespace_forbidden_characters"
    assert exc.context == {"namespace": "with/slash"}
    assert resolve_error_message(exc) == tr(exc.translated_message, **(exc.context or {}))


def test_google_drive_execute_redacts_untyped_upstream_exception() -> None:
    provider = _provider()

    with pytest.raises(OutboundStorageNetworkError) as raised:
        provider._execute(object(), action="files.list")

    exc = raised.value
    assert exc.__cause__ is None
    assert exc.__context__ is None
    assert exc.translated_message == "adapters.outbound.storage.google_drive.errors.request_failed"
    assert exc.context == {"action": "files.list", "status": "unknown"}
    assert "execute" not in str(exc)
    assert resolve_error_message(exc) == tr(exc.translated_message, **(exc.context or {}))
