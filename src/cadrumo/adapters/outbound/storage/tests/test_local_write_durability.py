"""Durability contracts for the local provider's replacement write and probe.

Two guarantees the provider documents but did not hold:

- ``put`` advertises an atomic payload/sidecar write. When the same object key
  arrived under a *new* label it removed the previous label's payload and
  sidecar *before* writing the replacement, so a failing replacement sidecar
  left neither the old object nor the new one on disk. The existing suite
  covers same-label sidecar safety, which never exercises that branch.
- ``probe`` documents ``writable=True`` only for a sentinel write/delete
  round-trip that succeeded. It swallowed a failing delete and still reported
  ``writable=True`` with ``detail="sentinel round-trip ok"``, while the Google
  provider reports ``writable=False`` on the equivalent failure.

Both are driven against a real temp-directory provider with a real induced
failure, not a patched internal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.directory_scan import DirectoryEntryKind, scan_directory
from .....core.hashing import sha256_hex
from .....tests.path_obstruction import obstructed_path
from .._local import LocalFileSystemProvider, _sidecar_filename
from .._records import ProviderKind
from ..errors import OutboundStorageError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_NAMESPACE = "durability"
_HMAC = "a" * 64


def _provider(tmp_path: Path) -> LocalFileSystemProvider:
    return LocalFileSystemProvider(tmp_path)


def _hash(payload: bytes) -> str:
    """Return the provider's stored content-hash form for *payload*."""
    return f"sha256-{sha256_hex(payload)}"


def _stored_files(tmp_path: Path) -> set[str]:
    namespace_dir = tmp_path / _NAMESPACE
    if not namespace_dir.is_dir():
        return set()
    return {entry.name for entry in scan_directory(namespace_dir, select=DirectoryEntryKind.FILES)}


class TestLabelDriftReplacement:
    """A failed replacement must never destroy the object it replaces."""

    def test_prior_object_survives_a_failed_replacement_sidecar(self, tmp_path: Path) -> None:
        provider = _provider(tmp_path)
        provider.put(_NAMESPACE, _HMAC, b"original-bytes", content_hash=_hash(b"original-bytes"), label="old")
        assert _stored_files(tmp_path), "fixture did not store the original object"

        # Induce a real sidecar write failure for the new label by occupying
        # its exact sidecar path, which no file write can replace. The name
        # comes from the production helper so the test cannot drift from the
        # provider's naming scheme.
        sidecar = tmp_path / _NAMESPACE / _sidecar_filename(_HMAC, "new")
        sidecar.parent.mkdir(parents=True, exist_ok=True)

        with obstructed_path(sidecar), pytest.raises(OutboundStorageError):
            provider.put(_NAMESPACE, _HMAC, b"replacement-bytes", content_hash=_hash(b"replacement-bytes"), label="new")

        payload, metadata = provider.get(_NAMESPACE, _HMAC)
        assert payload == b"original-bytes", "the previous good object was destroyed by a failed replacement"
        assert metadata.object_key_hmac == _HMAC

    def test_successful_label_drift_still_removes_the_stale_pair(self, tmp_path: Path) -> None:
        """The deferral must not leak the superseded label's files."""
        provider = _provider(tmp_path)
        provider.put(_NAMESPACE, _HMAC, b"original-bytes", content_hash=_hash(b"original-bytes"), label="old")
        provider.put(_NAMESPACE, _HMAC, b"replacement-bytes", content_hash=_hash(b"replacement-bytes"), label="new")

        remaining = _stored_files(tmp_path)
        assert not [name for name in remaining if "old" in name], f"stale label files leaked: {sorted(remaining)}"
        payload, _ = provider.get(_NAMESPACE, _HMAC)
        assert payload == b"replacement-bytes"


class TestProbeCleanupHonesty:
    """``writable`` must reflect the whole round-trip, delete included."""

    def test_probe_reports_writable_when_the_round_trip_succeeds(self, tmp_path: Path) -> None:
        report = _provider(tmp_path).probe()
        assert report.writable is True
        assert report.provider_kind is ProviderKind.LOCAL_FILESYSTEM

    def test_probe_refuses_writable_when_sentinel_cleanup_fails(self, tmp_path: Path) -> None:
        provider = _provider(tmp_path)

        def _failing_delete(namespace: str, object_key_hmac: str) -> bool:
            raise PermissionError("sentinel delete refused by the filesystem")

        # Replace the provider's own delete on this instance so the sentinel
        # cleanup genuinely fails; the write half still runs for real.
        object.__setattr__(provider, "delete", _failing_delete)

        report = provider.probe()
        assert report.writable is False, "probe claimed writable after the sentinel delete failed"
        assert "cleanup failed" in report.detail
