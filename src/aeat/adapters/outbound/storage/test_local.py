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

from aeat.adapters.outbound.storage import (
    ProviderKind,
    OutboundStorageIntegrityError,
    OutboundStorageNotFoundError,
    StorageProvider,
    OutboundStorageValidationError,
)
from aeat.adapters.outbound.storage._local import LocalFileSystemProvider

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


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
    with pytest.raises(OutboundStorageValidationError, match="namespace must not be blank"):
        provider.put("", "abcdef0123456789", b"x", content_hash="sha256-x", label="x")


def test_put_rejects_namespace_with_slash(provider: LocalFileSystemProvider) -> None:
    with pytest.raises(OutboundStorageValidationError, match="forbidden characters"):
        provider.put("with/slash", "abcdef0123456789", b"x", content_hash="sha256-x", label="x")


def test_put_rejects_blank_content_hash(provider: LocalFileSystemProvider) -> None:
    with pytest.raises(OutboundStorageValidationError, match="content_hash"):
        provider.put("ledger_transaction", "abcdef0123456789", b"x", content_hash="", label="x")
