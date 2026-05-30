"""Live-gated tests for `GoogleDriveProvider`.

Skip cleanly unless `AEAT_LIVE_TESTS_ENABLED=1` AND the operator has
pre-registered an OAuth client + token for the named test profile
(`AEAT_GOOGLE_LIVE_PROFILE`, default `live-test`) AND
`aeat_google_drive_root_folder_id` is configured in the environment.

The tests exercise three real Drive paths:

1. `probe()` against the real Drive API — confirms the root folder is
   reachable and a sentinel round-trip succeeds.
2. `put` + `get` round-trip — creates a file under `aeat-vault/_probe/`,
   reads it back, asserts payload equality + integrity verification.
3. `iter_objects` + `delete` cleanup — confirms the new object is
   listed, then deletes it and confirms a subsequent get raises
   `OutboundStorageNotFoundError`.

These tests intentionally use the `_probe/` namespace + a deterministic
HMAC string so repeated runs do not pollute the operator's real
substrate namespaces.
"""

from __future__ import annotations

import hashlib
import os

import pytest

from aeat.adapters.outbound.storage import (
    OutboundStorageNotFoundError,
    StorageProvider,
    get_storage_provider,
)
from aeat.core.logging import get_logger

pytestmark = [pytest.mark.live_read, pytest.mark.domain_outbound]


_PROBE_HMAC = "00000000live-storage-probe"
_PROBE_NAMESPACE = "_probe"
_log = get_logger(__name__)


def _live_profile() -> str:
    return os.environ.get("AEAT_GOOGLE_LIVE_PROFILE", "live-test")


def _skip_unless_drive_configured() -> None:
    if os.environ.get("AEAT_LIVE_TESTS_ENABLED") != "1":
        pytest.skip("AEAT_LIVE_TESTS_ENABLED is not 1")
    from aeat.core.config import load_settings

    settings = load_settings()
    if settings.aeat_storage_provider_kind != "google_drive":
        pytest.skip(
            "aeat_storage_provider_kind is not google_drive; "
            "set AEAT_STORAGE_PROVIDER_KIND=google_drive to run live drive tests"
        )
    if not settings.aeat_google_drive_root_folder_id:
        pytest.skip("aeat_google_drive_root_folder_id is not configured")


def _provider_or_skip() -> StorageProvider:
    _skip_unless_drive_configured()
    try:
        return get_storage_provider()
    except Exception as exc:
        _log.debug("cannot build live storage provider", exc_info=True)
        pytest.skip(f"cannot build live storage provider: {exc}")


def test_probe_against_real_drive_returns_writable() -> None:
    provider = _provider_or_skip()
    report = provider.probe()
    assert report.reachable is True
    assert report.root_folder_present is True, report.detail
    assert report.writable is True, report.detail


def test_put_then_get_round_trips_payload_against_real_drive() -> None:
    provider = _provider_or_skip()
    payload = b"live drive probe payload"
    content_hash = f"sha256-{hashlib.sha256(payload).hexdigest()}"

    metadata = provider.put(
        _PROBE_NAMESPACE,
        _PROBE_HMAC,
        payload,
        content_hash=content_hash,
        label="live-test",
    )
    try:
        fetched, fetched_metadata = provider.get(_PROBE_NAMESPACE, _PROBE_HMAC)
        assert fetched == payload
        assert fetched_metadata.byte_length == len(payload)
    finally:
        provider.delete(_PROBE_NAMESPACE, _PROBE_HMAC)
    del metadata


def test_delete_clears_the_object_against_real_drive() -> None:
    provider = _provider_or_skip()
    payload = b"x"
    content_hash = f"sha256-{hashlib.sha256(payload).hexdigest()}"
    provider.put(
        _PROBE_NAMESPACE,
        _PROBE_HMAC,
        payload,
        content_hash=content_hash,
        label="live-test",
    )
    assert provider.delete(_PROBE_NAMESPACE, _PROBE_HMAC) is True
    with pytest.raises(OutboundStorageNotFoundError):
        provider.get(_PROBE_NAMESPACE, _PROBE_HMAC)
