"""Unit coverage for Google Drive storage provider boundaries.

These tests cover refusal paths that happen before a Drive service is
constructed. They do not fake the Drive API or patch dependencies.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .....core.errors import resolve_error_message
from .....core.i18n import tr
from .. import OutboundStorageNetworkError, OutboundStorageValidationError
from .._google_drive import GoogleDriveProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _provider() -> GoogleDriveProvider:
    return GoogleDriveProvider(credentials=object(), root_folder_id="drive-root", vault_folder_name="aeat-vault")


def test_google_drive_module_does_not_construct_settings_at_import_time() -> None:
    tree = ast.parse(Path(__file__).parent.parent.joinpath("_google_drive.py").read_text(encoding="utf-8"))
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"Settings", "_Settings"}
    ]

    assert offenders == []


def test_google_drive_provider_rejects_blank_root_with_localized_message() -> None:
    with pytest.raises(OutboundStorageValidationError) as raised:
        GoogleDriveProvider(credentials=object(), root_folder_id=" ", vault_folder_name="aeat-vault")

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage.google_drive.errors.root_folder_id_blank"
    assert exc.context == {"root_folder_id": " "}
    assert resolve_error_message(exc) == tr(exc.translated_message, **(exc.context or {}))


def test_google_drive_provider_rejects_blank_vault_folder_with_localized_message() -> None:
    with pytest.raises(OutboundStorageValidationError) as raised:
        GoogleDriveProvider(credentials=object(), root_folder_id="drive-root", vault_folder_name=" ")

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage.google_drive.errors.vault_folder_name_blank"
    assert resolve_error_message(exc) == tr(exc.translated_message, **(exc.context or {}))


def test_google_drive_provider_rejects_blank_namespace_before_service_construction() -> None:
    with pytest.raises(OutboundStorageValidationError) as raised:
        _provider().put("", "a" * 64, b"x", content_hash="sha256-x", label="x")

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage.google_drive.errors.namespace_blank"
    assert resolve_error_message(exc) == tr(exc.translated_message, **(exc.context or {}))


def test_google_drive_provider_rejects_forbidden_namespace_before_service_construction() -> None:
    with pytest.raises(OutboundStorageValidationError) as raised:
        _provider().put("with/slash", "a" * 64, b"x", content_hash="sha256-x", label="x")

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage.google_drive.errors.namespace_forbidden_characters"
    assert exc.context == {"namespace": "with/slash"}
    assert resolve_error_message(exc) == tr(exc.translated_message, **(exc.context or {}))


def test_google_drive_provider_rejects_blank_hmac_before_service_construction() -> None:
    with pytest.raises(OutboundStorageValidationError) as raised:
        _provider().put("ledger_transaction", " ", b"x", content_hash="sha256-x", label="x")

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage.google_drive.errors.object_key_hmac_blank"
    assert resolve_error_message(exc) == tr(exc.translated_message, **(exc.context or {}))


def test_google_drive_provider_rejects_blank_content_hash_before_service_construction() -> None:
    with pytest.raises(OutboundStorageValidationError) as raised:
        _provider().put("ledger_transaction", "a" * 64, b"x", content_hash=" ", label="x")

    exc = raised.value
    assert exc.translated_message == "adapters.outbound.storage.google_drive.errors.content_hash_blank"
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
