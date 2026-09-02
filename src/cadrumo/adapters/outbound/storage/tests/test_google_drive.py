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

from .....core.errors.error_codes import resolve_error_message
from .....core.i18n import tr
from .....core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from .....tests.google_credentials import unused_google_credentials
from ...google.tests.drive_media_server import drive_files_list_endpoint
from .._google_drive import GoogleDriveProvider
from .._google_drive_metadata import drive_storage_content_hash
from ..errors import OutboundStorageIntegrityError, OutboundStorageNetworkError, OutboundStorageValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _assert_drive_verdict(
    error: OutboundStorageValidationError,
    condition_id: str,
    facts: dict[str, str | bool],
    provenance: ActionEvidenceProvenance = ActionEvidenceProvenance.RUNTIME_OBSERVATION,
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
    assert evidence.provenance is provenance
    assert dict(evidence.values) == facts


def _provider() -> GoogleDriveProvider:
    return GoogleDriveProvider(
        credentials=unused_google_credentials(), root_folder_id="drive-root", vault_folder_name="cadrumo-vault"
    )


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
    ("provider_kwargs", "message", "context", "condition_id", "facts"),
    (
        (
            {"credentials": object(), "root_folder_id": " ", "vault_folder_name": "cadrumo-vault"},
            "adapters.outbound.storage.google_drive.errors.root_folder_id_blank",
            {"root_folder_id": " "},
            "storage.google_drive.root_folder_id.present",
            {"backend": "google_drive", "field": "root_folder_id", "valid": False},
        ),
        (
            {"credentials": object(), "root_folder_id": "drive-root", "vault_folder_name": " "},
            "adapters.outbound.storage.google_drive.errors.vault_folder_name_blank",
            None,
            "storage.google_drive.vault_folder_name.valid",
            {"backend": "google_drive", "field": "vault_folder_name", "valid": False},
        ),
    ),
    ids=("blank-root-folder", "blank-vault-folder"),
)
def test_google_drive_provider_rejects_blank_constructor_values_with_localized_message(
    provider_kwargs: dict[str, object],
    message: str,
    context: dict[str, str] | None,
    condition_id: str,
    facts: dict[str, str | bool],
) -> None:
    with pytest.raises(OutboundStorageValidationError) as raised:
        kwargs: Any = provider_kwargs
        GoogleDriveProvider(**kwargs)

    exc = raised.value
    assert exc.translated_message == message
    assert exc.translated_message is not None
    assert exc.context == context
    _assert_drive_verdict(exc, condition_id, facts)
    assert resolve_error_message(exc) == tr(exc.translated_message, **(exc.context or {}))


def test_google_drive_provider_refuses_the_former_product_vault_before_service_construction() -> None:
    """The legacy Drive folder is never adopted as Cadrumo state."""
    with pytest.raises(OutboundStorageValidationError) as raised:
        GoogleDriveProvider(
            credentials=unused_google_credentials(), root_folder_id="drive-root", vault_folder_name="aeat-vault"
        )

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage.google_drive.errors.former_vault_folder"
    assert exc.context == {"vault_folder_name": "aeat-vault"}
    assert exc.context is not None
    _assert_drive_verdict(
        exc,
        "storage.google_drive.vault_folder_name.valid",
        {"backend": "google_drive", "field": "vault_folder_name", "valid": False},
    )
    assert resolve_error_message(exc) == tr(exc.translated_message, **exc.context)


def test_google_drive_read_metadata_requires_the_same_typed_app_properties_contract() -> None:
    with pytest.raises(OutboundStorageIntegrityError, match="appProperties"):
        drive_storage_content_hash({"id": "drive-file", "appProperties": {"content_hash": "sha256-x"}})


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


def test_vault_resolution_refuses_a_vault_name_entry_that_is_not_a_folder() -> None:
    with drive_files_list_endpoint(
        pages=(
            {
                "files": [
                    {
                        "id": "not-a-folder",
                        "name": "cadrumo-vault",
                        "mimeType": "application/octet-stream",
                    }
                ]
            },
        )
    ) as endpoint:
        provider = _provider()
        provider._service = endpoint.service
        with pytest.raises(OutboundStorageValidationError) as raised:
            provider._resolve_vault_folder()

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage.google_drive.errors.vault_entry_not_folder"
    _assert_drive_verdict(
        exc,
        "storage.google_drive.vault_entry.folder",
        {"backend": "google_drive", "field": "vault_folder_entry", "valid": False},
    )


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
    "app_properties",
    (
        {"namespace": "ledger_transaction", "object_key_hmac": "a" * 64, "content_hash": "sha256-a"},
        {
            "cadrumo_vault_app": "foreign",
            "namespace": "ledger_transaction",
            "object_key_hmac": "a" * 64,
            "content_hash": "sha256-a",
        },
        {"cadrumo_vault_app": "cadrumo", "namespace": "ledger_transaction", "content_hash": "sha256-a"},
    ),
    ids=("missing-ownership-marker", "foreign-ownership-marker", "missing-full-object-key"),
)
def test_iter_objects_refuses_malformed_storage_app_properties(
    app_properties: dict[str, str],
) -> None:
    """A generated Drive listing cannot promote malformed metadata to storage state."""
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
            {
                "files": [
                    {
                        "id": "namespace-id",
                        "name": "ledger_transaction",
                        "appProperties": {"cadrumo_vault_app": "cadrumo"},
                    }
                ]
            },
            {
                "files": [
                    {
                        "id": "object-id",
                        "name": "aaaaaaaa--payload.bin",
                        "size": "1",
                        "modifiedTime": "2026-08-02T01:45:29Z",
                        "appProperties": app_properties,
                    }
                ]
            },
        )
    ) as endpoint:
        provider = _provider()
        provider._service = endpoint.service

        with pytest.raises(OutboundStorageIntegrityError, match="appProperties"):
            list(provider.iter_objects("ledger_transaction"))

    assert len(endpoint.requested_queries) == 3


@pytest.mark.parametrize(
    ("put_kwargs", "message", "condition_id", "facts"),
    (
        (
            {"namespace": "", "object_key_hmac": "a" * 64, "payload": b"x", "content_hash": "sha256-x", "label": "x"},
            "adapters.outbound.storage.google_drive.errors.namespace_blank",
            "storage.google_drive.namespace.valid",
            {"backend": "google_drive", "field": "namespace", "valid": False},
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
            "storage.key.present",
            {"backend": "google_drive", "field": "object_key_hmac", "valid": False},
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
            "storage.google_drive.content_hash.present",
            {"backend": "google_drive", "field": "content_hash", "valid": False},
        ),
    ),
    ids=("blank-namespace", "blank-object-hmac", "blank-content-hash"),
)
def test_google_drive_provider_rejects_blank_put_values_before_service_construction(
    put_kwargs: dict[str, object],
    message: str,
    condition_id: str,
    facts: dict[str, str | bool],
) -> None:
    with pytest.raises(OutboundStorageValidationError) as raised:
        kwargs: Any = put_kwargs
        _provider().put(**kwargs)

    exc = raised.value
    assert exc.translated_message == message
    assert exc.translated_message is not None
    _assert_drive_verdict(exc, condition_id, facts)
    assert resolve_error_message(exc) == tr(exc.translated_message, **(exc.context or {}))


def test_google_drive_provider_rejects_forbidden_namespace_before_service_construction() -> None:
    with pytest.raises(OutboundStorageValidationError) as raised:
        _provider().put("with/slash", "a" * 64, b"x", content_hash="sha256-x", label="x")

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage.google_drive.errors.namespace_forbidden_characters"
    assert exc.context == {"namespace": "with/slash"}
    _assert_drive_verdict(
        exc,
        "storage.google_drive.namespace.valid",
        {"backend": "google_drive", "field": "namespace", "valid": False},
    )
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
