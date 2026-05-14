"""Tests for `InMemoryDriveProvider`."""

from __future__ import annotations

import hashlib

import pytest

from aeat.adapters.outbound.storage import (
    ProviderKind,
    StorageIntegrityError,
    StorageNotFoundError,
    StorageProvider,
    StorageValidationError,
)
from aeat.adapters.outbound.storage._testing import InMemoryDriveProvider

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def _hash(payload: bytes) -> str:
    return f"sha256-{hashlib.sha256(payload).hexdigest()}"


@pytest.fixture
def provider() -> InMemoryDriveProvider:
    return InMemoryDriveProvider()


def test_in_memory_provider_satisfies_runtime_protocol(provider: InMemoryDriveProvider) -> None:
    assert isinstance(provider, StorageProvider)


def test_put_returns_metadata_with_drive_shaped_object_id(provider: InMemoryDriveProvider) -> None:
    metadata = provider.put(
        "ledger_transaction",
        "abcdef0123456789",
        b"x",
        content_hash=_hash(b"x"),
        label="x",
    )
    # Drive `fileId` values are URL-safe strings, never filesystem paths.
    assert "/" not in metadata.provider_object_id
    assert "\\" not in metadata.provider_object_id
    assert len(metadata.provider_object_id) >= 8


def test_get_round_trips_payload_and_metadata(provider: InMemoryDriveProvider) -> None:
    payload = b"hello in-memory"
    provider.put(
        "ledger_transaction",
        "abcdef0123456789",
        payload,
        content_hash=_hash(payload),
        label="x",
    )
    fetched, metadata = provider.get("ledger_transaction", "abcdef0123456789")
    assert fetched == payload
    assert metadata.byte_length == len(payload)


def test_get_raises_storage_not_found_when_namespace_missing(provider: InMemoryDriveProvider) -> None:
    with pytest.raises(StorageNotFoundError):
        provider.get("never_seen", "abcdef0123456789")


def test_get_raises_storage_not_found_when_object_missing(provider: InMemoryDriveProvider) -> None:
    provider.put(
        "ledger_transaction",
        "deadbeefdeadbeef",
        b"x",
        content_hash=_hash(b"x"),
        label="x",
    )
    with pytest.raises(StorageNotFoundError):
        provider.get("ledger_transaction", "0000000000000000")


def test_get_refuses_payload_when_stored_hash_diverges(provider: InMemoryDriveProvider) -> None:
    """Tests can inject a wrong hash; get() catches the mismatch."""

    metadata = provider.put(
        "ledger_transaction",
        "abcdef0123456789",
        b"original",
        content_hash=_hash(b"different"),  # deliberately wrong
        label="x",
    )
    del metadata
    with pytest.raises(StorageIntegrityError):
        provider.get("ledger_transaction", "abcdef0123456789")


def test_delete_returns_true_when_object_existed(provider: InMemoryDriveProvider) -> None:
    provider.put(
        "ledger_transaction",
        "abcdef0123456789",
        b"x",
        content_hash=_hash(b"x"),
        label="x",
    )
    assert provider.delete("ledger_transaction", "abcdef0123456789") is True
    with pytest.raises(StorageNotFoundError):
        provider.get("ledger_transaction", "abcdef0123456789")


def test_delete_returns_false_when_object_absent(provider: InMemoryDriveProvider) -> None:
    assert provider.delete("ledger_transaction", "abcdef0123456789") is False


def test_iter_namespaces_returns_insertion_order(provider: InMemoryDriveProvider) -> None:
    provider.put("b", "0000000000000001", b"x", content_hash=_hash(b"x"), label="x")
    provider.put("a", "0000000000000002", b"x", content_hash=_hash(b"x"), label="x")
    provider.put("c", "0000000000000003", b"x", content_hash=_hash(b"x"), label="x")
    assert list(provider.iter_namespaces()) == ["b", "a", "c"]


def test_iter_namespaces_retains_emptied_namespaces(provider: InMemoryDriveProvider) -> None:
    provider.put("ledger_transaction", "abcdef0123456789", b"x", content_hash=_hash(b"x"), label="x")
    provider.delete("ledger_transaction", "abcdef0123456789")
    # Drive retains the empty folder; in-memory mirrors that.
    assert "ledger_transaction" in list(provider.iter_namespaces())


def test_iter_objects_yields_every_object(provider: InMemoryDriveProvider) -> None:
    for key in ("aaaaaaaa00000001", "bbbbbbbb00000002"):
        provider.put("ledger_transaction", key, b"x", content_hash=_hash(b"x"), label="x")
    objects = list(provider.iter_objects("ledger_transaction"))
    keys = sorted(obj.object_key_hmac for obj in objects)
    assert keys == ["aaaaaaaa00000001", "bbbbbbbb00000002"]


def test_iter_objects_raises_for_missing_namespace(provider: InMemoryDriveProvider) -> None:
    with pytest.raises(StorageNotFoundError):
        list(provider.iter_objects("never_seen"))


def test_probe_returns_in_memory_kind(provider: InMemoryDriveProvider) -> None:
    report = provider.probe()
    assert report.provider_kind == ProviderKind.IN_MEMORY
    assert report.reachable is True
    assert report.writable is True
    assert report.read_only is False


def test_probe_read_only_reports_writable_false(provider: InMemoryDriveProvider) -> None:
    report = provider.probe(read_only=True)
    assert report.read_only is True
    assert report.writable is False


def test_put_rejects_blank_namespace(provider: InMemoryDriveProvider) -> None:
    with pytest.raises(StorageValidationError):
        provider.put("", "abcdef0123456789", b"x", content_hash="sha256-x", label="x")


def test_put_rejects_blank_hmac(provider: InMemoryDriveProvider) -> None:
    with pytest.raises(StorageValidationError):
        provider.put("ledger_transaction", "", b"x", content_hash="sha256-x", label="x")


def test_put_rejects_blank_content_hash(provider: InMemoryDriveProvider) -> None:
    with pytest.raises(StorageValidationError):
        provider.put("ledger_transaction", "abcdef0123456789", b"x", content_hash="", label="x")


def test_overwrite_replaces_payload_and_metadata(provider: InMemoryDriveProvider) -> None:
    """A second put() under the same key returns fresh metadata and replaces the payload."""

    metadata_v1 = provider.put(
        "ledger_transaction",
        "abcdef0123456789",
        b"v1",
        content_hash=_hash(b"v1"),
        label="x",
    )
    metadata_v2 = provider.put(
        "ledger_transaction",
        "abcdef0123456789",
        b"v2",
        content_hash=_hash(b"v2"),
        label="x",
    )
    assert metadata_v1.provider_object_id != metadata_v2.provider_object_id
    fetched, _ = provider.get("ledger_transaction", "abcdef0123456789")
    assert fetched == b"v2"
