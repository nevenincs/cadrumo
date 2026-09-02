"""A failed local delete leaves the pair, never half of it.

``delete`` unlinked the payload first and the sidecar second inside one
``try``. A sidecar cleanup that failed after the payload was already gone
raised while leaving nothing to retry: ``iter_objects`` no longer reported the
object, ``get`` could not read it, and the orphaned sidecar path then blocked a
re-``put`` under the same key. The object became un-deletable, un-readable and
un-writable at once — a distinct failure from the write-replacement and
metadata-integrity paths, because here the delete itself destroyed one half
before the other was durably removed.

Scope note, so the coverage is not read as wider than it is: the sidecar-side
failure is driven end-to-end through ``delete`` below, because a sidecar that
cannot be unlinked is reproducible on every platform. The payload-side failure
is not — a filesystem that refuses one unlink and permits its sibling needs a
platform-specific mechanism (an open handle on Windows, a mode bit that POSIX
ignores for unlink) — so its rollback is exercised against the real filesystem
through ``_restore_sidecar`` directly rather than through a mechanism that
would only fire on one operating system.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from .....tests.path_obstruction import obstructed_path
from ..errors import OutboundStoragePermissionError
from ..local import LocalFileSystemProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_NAMESPACE = "ledger_transaction"
_HMAC = "abcdef0123456789"
_PAYLOAD = b"delete atomicity probe"


def _hash(payload: bytes) -> str:
    return f"sha256-{hashlib.sha256(payload).hexdigest()}"


def _store(provider: LocalFileSystemProvider) -> tuple[Path, Path]:
    """Write one real object and return ``(payload_path, sidecar_path)``."""
    metadata = provider.put(
        _NAMESPACE,
        _HMAC,
        _PAYLOAD,
        content_hash=_hash(_PAYLOAD),
        label="delete-probe",
    )
    target = Path(metadata.provider_object_id)
    return target, target.with_name(target.stem + ".meta.json")


def test_a_failed_sidecar_removal_leaves_the_payload_on_disk(provider: LocalFileSystemProvider) -> None:
    """The regression: the payload used to be gone before the sidecar was tried.

    This is the whole finding in one assertion. Removing the payload first
    meant a sidecar failure destroyed the only half that could not be
    reconstructed, so the operator was left with a raised error and no object.

    The obstruction is refused by ``unlink`` on every platform this ships to --
    as :exc:`PermissionError` on Windows and :exc:`IsADirectoryError` on Linux.
    That the two differ is the reason the provider guards on :exc:`OSError`:
    the narrower catch let the Linux shape escape untranslated.
    """
    target, sidecar = _store(provider)

    with obstructed_path(sidecar), pytest.raises(OutboundStoragePermissionError):
        provider.delete(_NAMESPACE, _HMAC)

    assert target.is_file()
    assert target.read_bytes() == _PAYLOAD


def test_the_object_is_still_deletable_after_the_obstruction_clears(provider: LocalFileSystemProvider) -> None:
    """A failed delete is a retryable one.

    Pre-fix there was nothing left to retry against: the payload had already
    been unlinked, so the second call returned ``False`` while the orphaned
    sidecar path stayed behind forever.
    """
    target, sidecar = _store(provider)

    with obstructed_path(sidecar), pytest.raises(OutboundStoragePermissionError):
        provider.delete(_NAMESPACE, _HMAC)

    assert provider.delete(_NAMESPACE, _HMAC) is True
    assert not target.exists()
    assert not sidecar.exists()


def test_the_object_is_still_readable_after_the_obstruction_clears(provider: LocalFileSystemProvider) -> None:
    """The pair survives intact, so the object is not merely present but usable."""
    _, sidecar = _store(provider)

    with obstructed_path(sidecar), pytest.raises(OutboundStoragePermissionError):
        provider.delete(_NAMESPACE, _HMAC)

    payload, metadata = provider.get(_NAMESPACE, _HMAC)

    assert payload == _PAYLOAD
    assert metadata.object_key_hmac == _HMAC


def test_the_object_can_be_re_put_after_the_obstruction_clears(provider: LocalFileSystemProvider) -> None:
    """A same-key write is not blocked by the wreckage of a failed delete."""
    _, sidecar = _store(provider)

    with obstructed_path(sidecar), pytest.raises(OutboundStoragePermissionError):
        provider.delete(_NAMESPACE, _HMAC)

    replacement = b"written after a failed delete"
    provider.put(
        _NAMESPACE,
        _HMAC,
        replacement,
        content_hash=_hash(replacement),
        label="delete-probe",
    )

    payload, _ = provider.get(_NAMESPACE, _HMAC)
    assert payload == replacement


def test_a_successful_delete_still_removes_both_halves(provider: LocalFileSystemProvider) -> None:
    """The positive control: reordering must not leave the sidecar behind.

    Without it every assertion above would still hold if ``delete`` had simply
    stopped deleting anything.
    """
    target, sidecar = _store(provider)

    assert provider.delete(_NAMESPACE, _HMAC) is True
    assert not target.exists()
    assert not sidecar.exists()
    assert list(provider.iter_objects(_NAMESPACE)) == []


def test_deleting_an_absent_object_is_still_idempotent(provider: LocalFileSystemProvider) -> None:
    """A second delete reports absence rather than raising."""
    _store(provider)

    assert provider.delete(_NAMESPACE, _HMAC) is True
    assert provider.delete(_NAMESPACE, _HMAC) is False


def test_a_payload_only_object_is_still_cleanly_deleted(provider: LocalFileSystemProvider) -> None:
    """A pre-existing orphan without a sidecar deletes without a partner.

    The sidecar-first ordering must not make its absence an error: ``missing_ok``
    is what keeps an already-half-removed pair collectable.
    """
    target, sidecar = _store(provider)
    sidecar.unlink()

    assert provider.delete(_NAMESPACE, _HMAC) is True
    assert not target.exists()


def test_the_sidecar_restore_puts_back_byte_identical_metadata(provider: LocalFileSystemProvider) -> None:
    """The rollback used when the payload unlink is the half that fails.

    Driven against the real filesystem rather than through an induced
    payload-unlink failure, which has no cross-platform mechanism. What it
    pins is the property the rollback exists for: the sidecar that comes back
    is the one that was there, so a retried ``get`` finds the same digest,
    byte length and instant it would have found had the delete never run.
    """
    _, sidecar = _store(provider)
    original = sidecar.read_text(encoding="utf-8")
    sidecar.unlink()

    LocalFileSystemProvider._restore_sidecar(sidecar, original)

    assert sidecar.read_text(encoding="utf-8") == original
    assert json.loads(sidecar.read_text(encoding="utf-8"))["object_key_hmac"] == _HMAC
    payload, metadata = provider.get(_NAMESPACE, _HMAC)
    assert payload == _PAYLOAD
    assert metadata.object_key_hmac == _HMAC


def test_the_sidecar_restore_is_a_no_op_when_there_was_nothing_to_restore(
    provider: LocalFileSystemProvider,
) -> None:
    """A pair that never had a sidecar must not gain one on rollback."""
    _, sidecar = _store(provider)
    sidecar.unlink()

    LocalFileSystemProvider._restore_sidecar(sidecar, None)

    assert not sidecar.exists()
