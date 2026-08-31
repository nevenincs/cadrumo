"""Live-gated tests for `GoogleDriveProvider`.

Deselect unless `CADRUMO_LIVE_TESTS_ENABLED=1` AND the operator has
pre-registered an OAuth client + token for the named test profile
(`AEAT_GOOGLE_LIVE_PROFILE`, default `live-test`) AND
`cadrumo_google_drive_root_folder_id` is configured in the environment.

The tests exercise three real Drive paths:

1. `probe()` against the real Drive API — confirms the root folder is
   reachable and a sentinel round-trip succeeds.
2. `put` + `get` round-trip — creates a file under `cadrumo-vault/_probe/`,
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
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from .....core.logging import get_logger
from .....tests.live_gate import requires_live_enabled, requires_live_google_enabled
from .....tests.profile_capsule import open_test_profile_session
from .._factory import get_storage_provider
from .._mirror_manifest import (
    REMOTE_MIRROR_MANIFEST_NAMESPACE,
    inspect_remote_mirror_download,
    inspect_remote_mirror_upload,
    put_remote_mirror_namespace_manifest,
    remote_mirror_object_key_hmac,
)
from .._protocol import StorageProvider
from .._records import RemoteMirrorNamespaceManifest, RemoteMirrorObjectManifest
from ..errors import OutboundStorageNotFoundError

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


_PROBE_HMAC = "00000000live-storage-probe"
_PROBE_NAMESPACE = "_probe"
_log = get_logger(__name__)


def _live_profile() -> str:
    return os.environ.get("AEAT_GOOGLE_LIVE_PROFILE", "live-test")


def _require_drive_configured() -> None:
    requires_live_enabled()
    requires_live_google_enabled()
    from .....core.config import load_settings

    settings = load_settings()
    if settings.cadrumo_storage_provider_kind != "google_drive":
        pytest.fail(
            "cadrumo_storage_provider_kind is not google_drive; "
            "set CADRUMO_STORAGE_PROVIDER_KIND=google_drive after live Google opt-in",
        )
    if not settings.cadrumo_google_drive_root_folder_id:
        pytest.fail("cadrumo_google_drive_root_folder_id is not configured after live Google opt-in")


@contextmanager
def _active_profile_storage_session() -> Iterator[None]:
    from .....core.bucket_pointer import resolve_active_bucket_id

    active = resolve_active_bucket_id()
    if active is None:
        pytest.fail("live Google Drive tests require an active AEAT profile pointer")
    with open_test_profile_session(active):
        yield


def _provider_or_skip() -> StorageProvider:
    _require_drive_configured()
    try:
        with _active_profile_storage_session():
            return get_storage_provider()
    except Exception as exc:
        _log.debug("cannot build live storage provider", exc_info=True)
        pytest.fail(f"cannot build live storage provider after live gates passed: {exc}")


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


def test_remote_mirror_manifest_round_trips_against_real_drive_contents() -> None:
    provider = _provider_or_skip()
    payload = b"live drive remote mirror ciphertext payload"
    object_hmac = remote_mirror_object_key_hmac(_PROBE_NAMESPACE, b"remote-mirror-live-object")
    digest = hashlib.sha256(payload).hexdigest()
    revision_written_at = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)
    entry = RemoteMirrorObjectManifest(
        namespace=_PROBE_NAMESPACE,
        object_key_hmac=object_hmac,
        classification="diagnostic",
        schema_version=1,
        byte_length=len(payload),
        ciphertext_hash=digest,
        storage_revision_id="a" * 64,
        previous_storage_revision_id=None,
        row_written_at=revision_written_at,
        revision_written_at=revision_written_at,
    )
    manifest = RemoteMirrorNamespaceManifest(
        manifest_schema_version=1,
        namespace=_PROBE_NAMESPACE,
        object_count=1,
        latest_revision_id=entry.storage_revision_id,
        latest_revision_written_at=revision_written_at,
        objects=(entry,),
    )
    manifest_hmac: str | None = None
    provider.put(
        _PROBE_NAMESPACE,
        object_hmac,
        payload,
        content_hash=f"sha256-{digest}",
        label="live-remote-mirror",
    )
    try:
        manifest_metadata = put_remote_mirror_namespace_manifest(provider, manifest)
        manifest_hmac = manifest_metadata.object_key_hmac

        namespaces = set(provider.iter_namespaces())
        object_hmacs = {metadata.object_key_hmac for metadata in provider.iter_objects(_PROBE_NAMESPACE)}
        manifest_hmacs = {
            metadata.object_key_hmac for metadata in provider.iter_objects(REMOTE_MIRROR_MANIFEST_NAMESPACE)
        }
        manifest_payload, _ = provider.get(REMOTE_MIRROR_MANIFEST_NAMESPACE, manifest_hmac)
        reloaded_manifest = RemoteMirrorNamespaceManifest.model_validate_json(manifest_payload)

        assert _PROBE_NAMESPACE in namespaces
        assert REMOTE_MIRROR_MANIFEST_NAMESPACE in namespaces
        assert object_hmac in object_hmacs
        assert manifest_hmac in manifest_hmacs
        assert reloaded_manifest == manifest
        assert inspect_remote_mirror_upload(provider, manifest).ok is True
        assert inspect_remote_mirror_download(provider, manifest).ok is True
    finally:
        provider.delete(_PROBE_NAMESPACE, object_hmac)
        if manifest_hmac is not None:
            provider.delete(REMOTE_MIRROR_MANIFEST_NAMESPACE, manifest_hmac)
