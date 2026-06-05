"""Tests for `LocalFileSystemProvider`.

Exercises the full Protocol surface against a real `tmp_path` directory
tree. No mocks; every test reads + writes real files. The
in-memory backend has its own test module (`test_in_memory.py`); a
unified Protocol-conformance suite would run the same assertions
against both, but separating them keeps failures clearly localised.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from .....core.errors import ERROR_REGISTRY, build_error_envelope, resolve_error_message
from .....core.i18n import tr
from .. import (
    OutboundStorageIntegrityError,
    OutboundStorageNotFoundError,
    OutboundStorageValidationError,
    ProviderKind,
    StorageCorruptionError,
    StorageProvider,
)
from .._local import LocalFileSystemProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _hash(payload: bytes) -> str:
    return f"sha256-{hashlib.sha256(payload).hexdigest()}"


@pytest.fixture
def provider(tmp_path: Path) -> LocalFileSystemProvider:
    return LocalFileSystemProvider(tmp_path / "vault")


def test_local_provider_satisfies_runtime_protocol(provider: LocalFileSystemProvider) -> None:
    assert isinstance(provider, StorageProvider)


def test_put_creates_namespace_and_writes_payload_atomically(provider: LocalFileSystemProvider) -> None:
    payload = b"hello world"
    metadata = provider.put(
        "ledger_transaction",
        "abcdef0123456789",
        payload,
        content_hash=_hash(payload),
        label="payroll-2026Q1",
    )
    assert metadata.namespace == "ledger_transaction"
    assert metadata.byte_length == len(payload)
    target = Path(metadata.provider_object_id)
    assert target.is_file()
    assert target.name == "abcdef01--payroll-2026Q1.bin"
    sidecar = target.with_name(target.stem + ".meta.json")
    assert sidecar.is_file()


def test_put_writes_sidecar_with_canonical_fields(provider: LocalFileSystemProvider) -> None:
    payload = b"sidecar data"
    metadata = provider.put(
        "ledger_transaction",
        "abcdef0123456789",
        payload,
        content_hash=_hash(payload),
        label="record",
    )
    sidecar_path = Path(metadata.provider_object_id).with_name(Path(metadata.provider_object_id).stem + ".meta.json")
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["namespace"] == "ledger_transaction"
    assert sidecar["object_key_hmac"] == "abcdef0123456789"
    assert sidecar["byte_length"] == len(payload)
    assert sidecar["content_hash"] == _hash(payload)
    assert "written_at" in sidecar


def test_get_round_trips_payload(provider: LocalFileSystemProvider) -> None:
    payload = b"round trip"
    provider.put(
        "ledger_transaction",
        "abcdef0123456789",
        payload,
        content_hash=_hash(payload),
        label="rt",
    )
    fetched, metadata = provider.get("ledger_transaction", "abcdef0123456789")
    assert fetched == payload
    assert metadata.byte_length == len(payload)


def test_get_raises_storage_not_found_for_missing_object(provider: LocalFileSystemProvider) -> None:
    provider.put(
        "ledger_transaction",
        "deadbeefdeadbeef",
        b"x",
        content_hash=_hash(b"x"),
        label="x",
    )
    with pytest.raises(OutboundStorageNotFoundError):
        provider.get("ledger_transaction", "0000000000000000")


def test_get_raises_storage_integrity_on_payload_tamper(provider: LocalFileSystemProvider) -> None:
    payload = b"genuine"
    metadata = provider.put(
        "ledger_transaction",
        "fedcba9876543210",
        payload,
        content_hash=_hash(payload),
        label="tamper",
    )
    Path(metadata.provider_object_id).write_bytes(b"tampered")
    with pytest.raises(OutboundStorageIntegrityError):
        provider.get("ledger_transaction", "fedcba9876543210")


def test_delete_returns_true_when_object_existed(provider: LocalFileSystemProvider) -> None:
    payload = b"x"
    provider.put(
        "ledger_transaction",
        "abcdef0123456789",
        payload,
        content_hash=_hash(payload),
        label="del",
    )
    assert provider.delete("ledger_transaction", "abcdef0123456789") is True
    with pytest.raises(OutboundStorageNotFoundError):
        provider.get("ledger_transaction", "abcdef0123456789")


def test_delete_returns_false_when_object_absent(provider: LocalFileSystemProvider) -> None:
    assert provider.delete("ledger_transaction", "abcdef0123456789") is False


def test_iter_namespaces_lists_every_subdirectory(provider: LocalFileSystemProvider) -> None:
    payload = b"x"
    provider.put("a", "abcdef0123456789", payload, content_hash=_hash(payload), label="x")
    provider.put("b", "fedcba9876543210", payload, content_hash=_hash(payload), label="x")
    namespaces = sorted(provider.iter_namespaces())
    assert namespaces == ["a", "b"]


def test_iter_objects_yields_metadata_for_every_object(provider: LocalFileSystemProvider) -> None:
    payload = b"x"
    for key, label in (("aaaaaaaa00000001", "first"), ("bbbbbbbb00000002", "second")):
        provider.put("ledger_transaction", key, payload, content_hash=_hash(payload), label=label)
    objects = list(provider.iter_objects("ledger_transaction"))
    assert len(objects) == 2
    keys = sorted(obj.object_key_hmac for obj in objects)
    assert keys == ["aaaaaaaa00000001", "bbbbbbbb00000002"]


def test_iter_objects_raises_for_missing_namespace(provider: LocalFileSystemProvider) -> None:
    with pytest.raises(OutboundStorageNotFoundError):
        list(provider.iter_objects("never_seen"))


def test_probe_read_only_does_not_touch_filesystem(tmp_path: Path) -> None:
    provider = LocalFileSystemProvider(tmp_path / "nonexistent")
    report = provider.probe(read_only=True)
    assert report.provider_kind == ProviderKind.LOCAL_FILESYSTEM
    assert report.reachable is True
    assert report.writable is False
    assert report.read_only is True
    # The root was created by probe (mkdir parents=True, exist_ok=True),
    # but no sentinel file was written.
    assert (tmp_path / "nonexistent").is_dir()
    assert not (tmp_path / "nonexistent" / "_probe").exists()


def test_probe_full_round_trip_writes_and_cleans_up_sentinel(provider: LocalFileSystemProvider) -> None:
    report = provider.probe()
    assert report.reachable is True
    assert report.writable is True
    assert report.read_only is False
    # Sentinel file is deleted after the round-trip; the _probe namespace
    # directory may persist but it must be empty of .bin files.
    probe_dir = provider.root / "_probe"
    if probe_dir.is_dir():
        assert not any(entry.suffix == ".bin" for entry in probe_dir.iterdir())


def test_put_with_relabel_replaces_existing_file(provider: LocalFileSystemProvider) -> None:
    payload = b"x"
    metadata_v1 = provider.put(
        "ledger_transaction",
        "abcdef0123456789",
        payload,
        content_hash=_hash(payload),
        label="v1",
    )
    metadata_v2 = provider.put(
        "ledger_transaction",
        "abcdef0123456789",
        payload,
        content_hash=_hash(payload),
        label="v2",
    )
    assert metadata_v1.provider_object_id != metadata_v2.provider_object_id
    assert not Path(metadata_v1.provider_object_id).exists()
    assert Path(metadata_v2.provider_object_id).exists()


def test_put_rejects_blank_namespace(provider: LocalFileSystemProvider) -> None:
    with pytest.raises(OutboundStorageValidationError, match="namespace must not be blank") as raised:
        provider.put("", "abcdef0123456789", b"x", content_hash="sha256-x", label="x")
    assert raised.value.translated_message == "adapters.outbound.storage.local.errors.namespace_blank"
    assert resolve_error_message(raised.value) == tr(raised.value.translated_message)


def test_put_rejects_namespace_with_slash(provider: LocalFileSystemProvider) -> None:
    with pytest.raises(OutboundStorageValidationError, match="forbidden characters") as raised:
        provider.put("with/slash", "abcdef0123456789", b"x", content_hash="sha256-x", label="x")
    assert raised.value.translated_message == "adapters.outbound.storage.local.errors.namespace_forbidden_characters"
    assert raised.value.context == {"namespace": "with/slash"}
    assert resolve_error_message(raised.value) == tr(raised.value.translated_message, **(raised.value.context or {}))


def test_put_rejects_blank_content_hash(provider: LocalFileSystemProvider) -> None:
    with pytest.raises(OutboundStorageValidationError, match="content_hash") as raised:
        provider.put("ledger_transaction", "abcdef0123456789", b"x", content_hash="", label="x")
    assert raised.value.translated_message == "adapters.outbound.storage.local.errors.content_hash_blank"
    assert resolve_error_message(raised.value) == tr(raised.value.translated_message)


def test_get_rejects_non_object_sidecar_with_localized_integrity_error(provider: LocalFileSystemProvider) -> None:
    payload = b"sidecar-shape"
    metadata = provider.put(
        "ledger_transaction",
        "11223344aabbccdd",
        payload,
        content_hash=_hash(payload),
        label="sidecar-shape",
    )
    obj_path = Path(metadata.provider_object_id)
    sidecar_path = obj_path.with_name(obj_path.stem + ".meta.json")
    sidecar_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

    with pytest.raises(OutboundStorageIntegrityError) as raised:
        provider.get("ledger_transaction", "11223344aabbccdd")

    assert raised.value.translated_message == "adapters.outbound.storage.local.errors.sidecar_not_object"
    assert raised.value.context == {"sidecar_path": str(sidecar_path)}
    assert resolve_error_message(raised.value) == tr(raised.value.translated_message, **(raised.value.context or {}))


# ---------------------------------------------------------------------------
# contract: StorageCorruptionError registry, envelope, and real read-path coverage
# ---------------------------------------------------------------------------


def test_storage_corruption_error_is_registered_in_error_registry() -> None:
    """StorageCorruptionError must have a bound ErrorCode in ERROR_REGISTRY."""
    assert "INTEGRITY_OUTBOUND_STORAGE_CORRUPTION" in ERROR_REGISTRY


def test_storage_corruption_error_round_trips_through_build_error_envelope() -> None:
    """build_error_envelope must produce a valid envelope for StorageCorruptionError."""
    err = StorageCorruptionError(
        "sidecar byte_length has unexpected type: <class 'list'>",
        context={"actual_type": "list"},
    )
    envelope = build_error_envelope(err)
    assert envelope.code == "INTEGRITY_OUTBOUND_STORAGE_CORRUPTION"
    assert envelope.retryable is False
    assert "actual_type" in (envelope.context or {})


def test_get_raises_storage_corruption_error_when_sidecar_byte_length_is_wrong_type(
    provider: LocalFileSystemProvider,
    tmp_path: Path,
) -> None:
    """The real read path must raise StorageCorruptionError when byte_length is a list."""
    payload = b"corruption-test-payload"
    metadata = provider.put(
        "ledger_transaction",
        "aabbccdd00112233",
        payload,
        content_hash=_hash(payload),
        label="corruption",
    )
    # Locate and corrupt the sidecar: replace byte_length int with a list.
    obj_path = Path(metadata.provider_object_id)
    sidecar_path = obj_path.with_name(obj_path.stem + ".meta.json")
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["byte_length"] = [42]  # unexpected type: list
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    with pytest.raises(StorageCorruptionError) as raised:
        provider.get("ledger_transaction", "aabbccdd00112233")
    assert raised.value.translated_message == "adapters.outbound.storage.local.errors.byte_length_invalid"
    assert resolve_error_message(raised.value) == tr(raised.value.translated_message, **(raised.value.context or {}))
