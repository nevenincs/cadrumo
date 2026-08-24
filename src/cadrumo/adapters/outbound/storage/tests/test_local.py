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
import os
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypedDict

import pytest

from .....core import ActionConditionality, NoRecoveryOutcome, iter_directory, scan_directory
from .....core.atomic_write import atomic_write_text
from .....core.errors import ERROR_REGISTRY, build_error_envelope, resolve_error_message
from .....core.i18n import tr
from .....tests.path_obstruction import obstructed_path
from .. import (
    OutboundStorageIntegrityError,
    OutboundStorageNotFoundError,
    OutboundStoragePathTooLongError,
    OutboundStorageValidationError,
    ProviderKind,
    StorageCorruptionError,
    StorageProvider,
)
from .._errors import OutboundStoragePermissionError
from .._local import LocalFileSystemProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _hash(payload: bytes) -> str:
    return f"sha256-{hashlib.sha256(payload).hexdigest()}"


def _assert_local_verdict(error: BaseException, condition_id: str, outcome: NoRecoveryOutcome) -> None:
    verdict = error.terminal_precondition_verdict
    assert verdict.failed_condition_id == condition_id
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.action is None
    assert verdict.no_recovery_outcome is outcome
    assert len(verdict.evidence) == 1


def test_local_provider_satisfies_runtime_protocol(provider: LocalFileSystemProvider) -> None:
    assert isinstance(provider, StorageProvider)


def test_local_sidecar_return_type_is_mapping() -> None:
    """The sidecar loader advertises its mapping boundary."""
    return_hint = LocalFileSystemProvider._load_sidecar.__annotations__.get("return")

    assert "Mapping" in str(return_hint)


def test_local_sidecar_runtime_returns_mapping(tmp_path: Path) -> None:
    """A well-formed sidecar is loaded through the real filesystem provider."""
    sidecar = tmp_path / "test.meta.json"
    payload: dict[str, object] = {"content_hash": "abc123", "byte_length": 42}
    sidecar.write_text(json.dumps(payload), encoding="utf-8")

    result = LocalFileSystemProvider(root=tmp_path)._load_sidecar(sidecar)

    assert isinstance(result, Mapping)
    assert result == payload


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


def test_put_uses_the_canonical_safe_provider_object_name(provider: LocalFileSystemProvider) -> None:
    """A real local write keeps the shared HMAC-prefix and label rendering contract."""
    payload = b"object-name-kernel"
    metadata = provider.put(
        "ledger_transaction",
        "abcdef0123456789",
        payload,
        content_hash=_hash(payload),
        label=" payroll Q1/2026 ",
    )

    target = Path(metadata.provider_object_id)
    assert target.is_file()
    assert target.name == "abcdef01--payroll-Q1-2026.bin"
    assert target.with_name(target.stem + ".meta.json").is_file()


def test_put_sidecar_write_is_atomic_and_preserves_prior_content_on_failure(
    provider: LocalFileSystemProvider,
) -> None:
    """A real induced sidecar-write failure never corrupts the prior sidecar.

    Exercises the exact atomic-write call `put()` now uses for the sidecar
    (`atomic_write_text`) directly against the sidecar path a real `put()`
    already wrote, rather than mocking or patching anything: a wrongly-typed
    payload genuinely raises inside the write, proving the prior good
    sidecar content survives byte-for-byte and no `*.tmp` sibling lingers.
    """
    payload = b"sidecar-atomicity-check"
    metadata = provider.put(
        "ledger_transaction",
        "99887766554433aa",
        payload,
        content_hash=_hash(payload),
        label="sidecar-atomic",
    )
    target = Path(metadata.provider_object_id)
    sidecar = target.with_name(target.stem + ".meta.json")
    original_sidecar_bytes = sidecar.read_bytes()

    invalid_text: Any = None
    with pytest.raises(AttributeError):
        atomic_write_text(sidecar, invalid_text, encoding="utf-8")

    assert sidecar.read_bytes() == original_sidecar_bytes
    assert scan_directory(sidecar.parent, pattern="*.tmp") == ()


def test_put_writes_payload_with_hardened_mode_and_no_tmp_leftover(provider: LocalFileSystemProvider) -> None:
    """The object payload write is the atomic-write helper's hardened tier."""
    payload = b"hardened-mode-check"
    metadata = provider.put(
        "ledger_transaction",
        "0011223344556677",
        payload,
        content_hash=_hash(payload),
        label="hardened-check",
    )
    target = Path(metadata.provider_object_id)
    if os.name != "nt":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert scan_directory(target.parent, pattern="*.tmp") == ()


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


def test_hmac_prefix_collision_refuses_every_operation_and_preserves_original(
    provider: LocalFileSystemProvider,
) -> None:
    """A real local collision cannot overwrite, read, or delete the first object."""
    namespace = "ledger_transaction"
    key_a = "abcdef12-AAAAAAAA"
    key_b = "abcdef12-BBBBBBBB"
    payload_a = b"payload-a"
    payload_b = b"payload-b"
    provider.put(namespace, key_a, payload_a, content_hash=_hash(payload_a), label="first")

    with pytest.raises(OutboundStorageIntegrityError, match="HMAC prefix collision"):
        provider.put(namespace, key_b, payload_b, content_hash=_hash(payload_b), label="second")
    with pytest.raises(OutboundStorageIntegrityError, match="HMAC prefix collision"):
        provider.get(namespace, key_b)
    with pytest.raises(OutboundStorageIntegrityError, match="HMAC prefix collision"):
        provider.delete(namespace, key_b)

    fetched, metadata = provider.get(namespace, key_a)
    assert fetched == payload_a
    assert metadata.object_key_hmac == key_a
    assert list(provider.iter_objects(namespace)) == [metadata]


def test_get_raises_storage_not_found_for_missing_object(provider: LocalFileSystemProvider) -> None:
    provider.put(
        "ledger_transaction",
        "deadbeefdeadbeef",
        b"x",
        content_hash=_hash(b"x"),
        label="x",
    )
    with pytest.raises(OutboundStorageNotFoundError) as raised:
        provider.get("ledger_transaction", "0000000000000000")
    _assert_local_verdict(raised.value, "storage.local.object.present", NoRecoveryOutcome.OPERATOR_DECISION)


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
    with pytest.raises(OutboundStorageIntegrityError) as raised:
        provider.get("ledger_transaction", "fedcba9876543210")
    _assert_local_verdict(raised.value, "storage.integrity.content_hash_matches", NoRecoveryOutcome.SAFETY)


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
    with pytest.raises(OutboundStorageNotFoundError) as raised:
        list(provider.iter_objects("never_seen"))
    _assert_local_verdict(raised.value, "storage.local.namespace.present", NoRecoveryOutcome.OPERATOR_DECISION)


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
        assert not any(entry.suffix == ".bin" for entry in iter_directory(probe_dir))


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


class _PutKwargs(TypedDict):
    """Keyword arguments for :meth:`LocalFileSystemProvider.put`, matching its real signature."""

    namespace: str
    object_key_hmac: str
    payload: bytes
    content_hash: str


_INVALID_STORAGE_KEY_CASES: tuple[tuple[_PutKwargs, str, str, dict[str, str] | None], ...] = (
    (
        {"namespace": "", "object_key_hmac": "abcdef0123456789", "payload": b"x", "content_hash": "sha256-x"},
        "namespace must not be blank",
        "adapters.outbound.storage.local.errors.namespace_blank",
        None,
    ),
    (
        {
            "namespace": "with/slash",
            "object_key_hmac": "abcdef0123456789",
            "payload": b"x",
            "content_hash": "sha256-x",
        },
        "forbidden characters",
        "adapters.outbound.storage.local.errors.namespace_forbidden_characters",
        {"namespace": "with/slash"},
    ),
    (
        {
            "namespace": "ledger_transaction",
            "object_key_hmac": "abcdef0123456789",
            "payload": b"x",
            "content_hash": "",
        },
        "content_hash",
        "adapters.outbound.storage.local.errors.content_hash_blank",
        None,
    ),
)


@pytest.mark.parametrize(
    ("put_kwargs", "match", "message", "context"),
    _INVALID_STORAGE_KEY_CASES,
    ids=("blank-namespace", "forbidden-namespace", "blank-content-hash"),
)
def test_put_rejects_invalid_storage_keys(
    provider: LocalFileSystemProvider,
    put_kwargs: _PutKwargs,
    match: str,
    message: str,
    context: dict[str, str] | None,
) -> None:
    with pytest.raises(OutboundStorageValidationError, match=match) as raised:
        provider.put(**put_kwargs, label="x")
    translated_message = raised.value.translated_message
    if translated_message is None:
        pytest.fail("expected a translated_message on the raised error")
    assert translated_message == message
    assert raised.value.context == context
    assert resolve_error_message(raised.value) == tr(translated_message, **(raised.value.context or {}))


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


def test_get_refuses_sidecar_byte_length_that_disagrees_with_payload(
    provider: LocalFileSystemProvider,
) -> None:
    """The real read path rejects a numeric sidecar length that misstates payload bytes."""

    payload = b"byte-length-integrity"
    metadata = provider.put(
        "ledger_transaction",
        "aabbccdd00112233",
        payload,
        content_hash=_hash(payload),
        label="byte-length",
    )
    object_path = Path(metadata.provider_object_id)
    sidecar_path = object_path.with_name(object_path.stem + ".meta.json")
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["byte_length"] = len(payload) + 1
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    with pytest.raises(OutboundStorageIntegrityError) as raised:
        provider.get("ledger_transaction", "aabbccdd00112233")

    assert raised.value.context is not None
    assert raised.value.context["stored_byte_length"] == str(len(payload) + 1)
    assert raised.value.context["actual_byte_length"] == str(len(payload))


# ---------------------------------------------------------------------------
# WIN-003: Windows MAX_PATH (long-path) classification on the write boundary
# ---------------------------------------------------------------------------


def test_path_too_long_error_is_registered_in_error_registry() -> None:
    """OutboundStoragePathTooLongError must have a bound ErrorCode in ERROR_REGISTRY."""
    assert "ERROR_OUTBOUND_STORAGE_PATH_TOO_LONG" in ERROR_REGISTRY


def test_path_too_long_error_round_trips_through_build_error_envelope() -> None:
    """build_error_envelope must produce a valid, localized envelope for the new error."""
    err = OutboundStoragePathTooLongError(
        "cannot write object payload to C:\\deep\\path: path exceeds the Windows MAX_PATH ceiling",
        context={"path": "C:\\deep\\path"},
        translated_message="adapters.outbound.storage.local.errors.payload_write_path_too_long",
    )
    envelope = build_error_envelope(err)
    assert envelope.code == "ERROR_OUTBOUND_STORAGE_PATH_TOO_LONG"
    assert envelope.retryable is False
    assert "path" in (envelope.context or {})
    assert err.translated_message is not None
    assert resolve_error_message(err) == tr(err.translated_message, **(err.context or {}))


def test_put_still_raises_conflict_for_a_real_non_long_path_oserror(
    provider: LocalFileSystemProvider,
    tmp_path: Path,
) -> None:
    """A genuine, unrelated OSError during the payload write is NOT misclassified as long-path.

    Reproduces a real (not mocked) write failure: the target object's
    sidecar path is pre-occupied by a real directory, so
    ``sidecar_path.write_text(...)`` raises a real ``OSError`` (Windows:
    ``PermissionError``/WinError 5; POSIX: ``IsADirectoryError``) carrying
    no long-path ``winerror`` signature. The cleanup path here only
    unlinks the already-committed ``target_path`` file (not the colliding
    directory), so the reproduction exercises the classification branch
    without tripping the pre-existing directory-vs-tmp-file cleanup
    ordering. Confirms the fallthrough for a genuinely unrelated failure
    never raises :class:`OutboundStoragePathTooLongError`.
    """
    payload = b"payload whose sidecar path is a real directory"
    hmac = "0011223344556677"
    label = "blocked"
    # Materialise the real namespace directory through the public API,
    # then pre-occupy the exact sidecar path this hmac/label pair resolves
    # to as a real directory so the real sidecar write step collides.
    provider.put("ledger_transaction", "ffffffffffffffff", b"seed", content_hash=_hash(b"seed"), label="seed")
    namespace_dir = tmp_path / "vault" / "ledger_transaction"
    sidecar_collision = namespace_dir / f"{hmac[:8]}--{label}.meta.json"

    with obstructed_path(sidecar_collision), pytest.raises(OutboundStoragePermissionError) as raised:
        provider.put("ledger_transaction", hmac, payload, content_hash=_hash(payload), label=label)
    assert not isinstance(raised.value, OutboundStoragePathTooLongError)
    assert raised.value.translated_message == "adapters.outbound.storage.local.errors.sidecar_write_failed"
