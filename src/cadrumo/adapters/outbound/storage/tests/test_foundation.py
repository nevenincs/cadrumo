"""Tests for the storage provider abstraction's foundation surface.

Covers the Protocol contract, the pydantic records, the `ProviderKind`
enum, and the typed `OutboundStorageError` hierarchy. Concrete backend
(`_local.py`, `_google_drive.py`) tests live in their own colocated test
modules.
"""

from __future__ import annotations

import importlib
import inspect
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from .....core.errors.hierarchy import CadrumoError, CoreError
from .._protocol import StorageProvider
from .._records import ProviderKind, ProviderObjectMetadata, ProviderProbeReport, RemoteMirrorObjectManifest
from ..errors import (
    OutboundStorageConflictError,
    OutboundStorageError,
    OutboundStorageIntegrityError,
    OutboundStorageNetworkError,
    OutboundStorageNotFoundError,
    OutboundStoragePermissionError,
    OutboundStorageQuotaError,
    OutboundStorageUnavailableError,
    OutboundStorageValidationError,
    StorageCorruptionError,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _metadata(**overrides: object) -> ProviderObjectMetadata:
    base: dict[str, object] = {
        "namespace": "ledger_transaction",
        "object_key_hmac": "abc123def456",
        "provider_object_id": "drive-file-id-xyz",
        "byte_length": 1024,
        "content_hash": "sha256-deadbeef",
        "written_at": datetime(2026, 5, 14, tzinfo=UTC),
    }
    base.update(overrides)
    return ProviderObjectMetadata.model_validate(base)


def _remote_object_manifest(**overrides: object) -> RemoteMirrorObjectManifest:
    base: dict[str, object] = {
        "namespace": "google_oauth_metadata",
        "object_key_hmac": "a" * 64,
        "classification": "secret",
        "schema_version": 1,
        "byte_length": 128,
        "ciphertext_hash": "b" * 64,
        "storage_revision_id": "c" * 64,
        "previous_storage_revision_id": "d" * 64,
        "revision_ancestor_ids": ("e" * 64,),
        "row_written_at": datetime(2026, 5, 14, tzinfo=UTC),
        "revision_written_at": datetime(2026, 5, 14, tzinfo=UTC),
    }
    base.update(overrides)
    return RemoteMirrorObjectManifest.model_validate(base)


def test_provider_kind_enum_values_are_stable() -> None:
    assert ProviderKind.LOCAL_FILESYSTEM.value == "local_filesystem"
    assert ProviderKind.GOOGLE_DRIVE.value == "google_drive"


def test_provider_object_metadata_round_trip() -> None:
    payload = _metadata()
    reloaded = ProviderObjectMetadata.model_validate_json(payload.model_dump_json())
    assert reloaded == payload


def test_provider_object_metadata_is_frozen() -> None:
    payload = _metadata()
    with pytest.raises(ValidationError, match="frozen"):
        payload.namespace = "other"


def test_provider_object_metadata_rejects_negative_byte_length() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        _metadata(byte_length=-1)


def test_provider_object_metadata_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra"):
        ProviderObjectMetadata.model_validate(
            {
                "namespace": "ledger_transaction",
                "object_key_hmac": "abc",
                "provider_object_id": "x",
                "byte_length": 0,
                "content_hash": "sha256-x",
                "written_at": datetime(2026, 5, 14, tzinfo=UTC),
                "unexpected": "value",
            },
        )


def test_provider_probe_report_defaults_root_folder_to_none() -> None:
    report = ProviderProbeReport(
        provider_kind=ProviderKind.LOCAL_FILESYSTEM,
        reachable=True,
        writable=True,
        read_only=False,
    )
    assert report.root_folder_present is None
    assert report.detail == ""


def test_provider_probe_report_read_only_mode_round_trip() -> None:
    report = ProviderProbeReport(
        provider_kind=ProviderKind.GOOGLE_DRIVE,
        reachable=True,
        writable=False,
        read_only=True,
        root_folder_present=True,
        detail="probe ran with read_only=True; sentinel round-trip skipped",
    )
    reloaded = ProviderProbeReport.model_validate_json(report.model_dump_json())
    assert reloaded == report
    assert reloaded.read_only is True
    assert reloaded.writable is False


def test_remote_mirror_object_manifest_rejects_malformed_revision_ancestor_id() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _remote_object_manifest(revision_ancestor_ids=("short",))

    (error,) = exc_info.value.errors()
    assert error["loc"] == ("revision_ancestor_ids", 0)
    assert error["type"] == "string_too_short"


def test_storage_error_hierarchy_unified() -> None:
    outbound_leaves = (
        OutboundStorageConflictError,
        OutboundStorageIntegrityError,
        OutboundStorageNetworkError,
        OutboundStorageNotFoundError,
        OutboundStoragePermissionError,
        OutboundStorageQuotaError,
        OutboundStorageUnavailableError,
        OutboundStorageValidationError,
    )
    for leaf in outbound_leaves:
        assert issubclass(leaf, OutboundStorageError), leaf.__name__
        assert issubclass(leaf, CadrumoError), leaf.__name__

    assert issubclass(StorageCorruptionError, CoreError)
    assert not issubclass(StorageCorruptionError, OutboundStorageError)


def test_storage_validation_error_is_value_error_subclass() -> None:
    assert issubclass(OutboundStorageValidationError, ValueError)


def test_storage_contracts_resolve_at_their_defining_modules_and_backends_stay_private() -> None:
    """Contracts stay reachable and named; concrete backends stay unexposed.

    This pinned the package root's ``__all__``. That root is now an inert
    namespace, so the same guarantee is asserted against the modules that
    define these symbols.

    Those defining modules are themselves underscore-private, which is the
    subject of the open mirror-manifest publicising step: consumers outside this
    package currently reach a private module. This test deliberately does NOT
    bless that shape -- it pins WHERE each contract lives so the publicising
    move has something to move against, and it keeps the backend-privacy half
    that still bites.
    """
    contracts = {
        "_protocol": ("StorageProvider",),
        "_records": ("ProviderKind",),
        "errors": ("OutboundStorageError",),
        "_factory": ("get_storage_provider",),
        "_mirror_manifest": (
            "REMOTE_MIRROR_MANIFEST_NAMESPACE",
            "REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION",
            "build_remote_mirror_namespace_manifest",
            "inspect_remote_mirror_upload",
            "inspect_remote_mirror_download",
        ),
    }
    for module_name, symbols in contracts.items():
        module = importlib.import_module(f"cadrumo.adapters.outbound.storage.{module_name}")
        for symbol in symbols:
            assert hasattr(module, symbol), f"{module_name}.{symbol}"

    root = importlib.import_module("cadrumo.adapters.outbound.storage")
    assert not root.__all__, "the storage package root is inert and must export nothing"

    for backend in ("GoogleDriveProvider", "LocalFileSystemProvider", "InMemoryDriveProvider"):
        assert not hasattr(root, backend), backend
        for module_name in ("_protocol", "_records", "_factory", "_mirror_manifest"):
            module = importlib.import_module(f"cadrumo.adapters.outbound.storage.{module_name}")
            assert not hasattr(module, backend), f"{module_name}.{backend}"


def test_storage_provider_protocol_keeps_synchronous_bytes_contract() -> None:
    methods = {
        name: inspect.signature(getattr(StorageProvider, name))
        for name in ("put", "get", "delete", "iter_namespaces", "iter_objects", "probe")
    }

    assert not inspect.iscoroutinefunction(StorageProvider.put)
    assert list(methods["put"].parameters) == [
        "self",
        "namespace",
        "object_key_hmac",
        "payload",
        "content_hash",
        "label",
    ]
    assert methods["put"].parameters["payload"].annotation == "bytes"
    assert methods["put"].parameters["content_hash"].kind is inspect.Parameter.KEYWORD_ONLY
    assert methods["put"].parameters["label"].kind is inspect.Parameter.KEYWORD_ONLY
    assert methods["put"].return_annotation == "ProviderObjectMetadata"

    assert methods["get"].return_annotation == "tuple[bytes, ProviderObjectMetadata]"
    assert methods["delete"].return_annotation == "bool"
    assert methods["iter_namespaces"].return_annotation == "Iterator[str]"
    assert methods["iter_objects"].return_annotation == "Iterator[ProviderObjectMetadata]"
    assert methods["probe"].parameters["read_only"].kind is inspect.Parameter.KEYWORD_ONLY
    assert methods["probe"].parameters["read_only"].default is False
    assert methods["probe"].return_annotation == "ProviderProbeReport"


def test_every_leaf_carries_a_registered_error_code() -> None:
    leaves = (
        OutboundStorageError,
        OutboundStorageValidationError,
        OutboundStorageNotFoundError,
        OutboundStorageConflictError,
        OutboundStoragePermissionError,
        OutboundStorageQuotaError,
        OutboundStorageNetworkError,
        OutboundStorageIntegrityError,
        OutboundStorageUnavailableError,
        StorageCorruptionError,
    )
    codes = {leaf.code.code for leaf in leaves}
    assert len(codes) == len(leaves), f"duplicate codes: {codes}"
    allowed_prefixes = (
        "FAIL_OUTBOUND_STORAGE",
        "REFUSED_OUTBOUND_STORAGE",
        "ERROR_OUTBOUND_STORAGE",
        "AUTH_OUTBOUND_STORAGE",
        "INTEGRITY_OUTBOUND_STORAGE",
    )
    for leaf in leaves:
        assert leaf.code.code.startswith(allowed_prefixes)


def test_real_local_filesystem_provider_satisfies_protocol(tmp_path: object) -> None:
    """Real `LocalFileSystemProvider` instance satisfies `runtime_checkable` Protocol."""

    from pathlib import Path

    from .._local import LocalFileSystemProvider

    provider = LocalFileSystemProvider(Path(str(tmp_path)) / "vault")
    assert isinstance(provider, StorageProvider)
