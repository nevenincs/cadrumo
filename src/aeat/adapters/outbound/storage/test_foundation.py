"""Tests for the storage provider abstraction's foundation surface.

Covers the Protocol contract, the three pydantic records, the
`ProviderKind` enum, and the typed `OutboundStorageError` hierarchy. Concrete
backend (`_local.py`, `_google_drive.py`, `_testing.py`) tests live in
their own colocated test modules.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aeat.adapters.outbound.storage import (
    ProviderKind,
    ProviderObjectMetadata,
    ProviderProbeReport,
    OutboundStorageConflictError,
    OutboundStorageError,
    OutboundStorageIntegrityError,
    OutboundStorageNetworkError,
    OutboundStorageNotFoundError,
    OutboundStoragePermissionError,
    StorageProvider,
    OutboundStorageQuotaError,
    OutboundStorageUnavailableError,
    OutboundStorageValidationError,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


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
        setattr(payload, "namespace", "other")  # noqa: B010 — exercise frozen-model __setattr__


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
            }
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


def test_storage_error_hierarchy_unified() -> None:
    for leaf in (
        OutboundStorageConflictError,
        OutboundStorageIntegrityError,
        OutboundStorageNetworkError,
        OutboundStorageNotFoundError,
        OutboundStoragePermissionError,
        OutboundStorageQuotaError,
        OutboundStorageUnavailableError,
        OutboundStorageValidationError,
    ):
        assert issubclass(leaf, OutboundStorageError), leaf.__name__


def test_storage_validation_error_is_value_error_subclass() -> None:
    assert issubclass(OutboundStorageValidationError, ValueError)


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

    from aeat.adapters.outbound.storage._local import LocalFileSystemProvider

    provider = LocalFileSystemProvider(Path(str(tmp_path)) / "vault")
    assert isinstance(provider, StorageProvider)
