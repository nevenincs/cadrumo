"""Precedence-chain tests for the active-profile resolver.

The resolver lives at
`aeat.application.workflow._models.resolve_active_bucket_id`. It
consults two precedence rungs in order:

1. `Settings.aeat_active_profile` (`AEAT_ACTIVE_PROFILE` env var, or
   an `override_settings(aeat_active_profile=...)` context manager).
2. The plaintext `<aeat-root>/active-profile` pointer file written
   by `register_active_profile` / `select_profile`.

A missing pointer + missing env override returns `None` so callers
that surface it to the operator can refuse with a typed
`NoActiveProfileError`.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from ....core import resolve_active_bucket_id
from ....core import BucketPointer
from ....core import write_pointer
from ....core.config import override_settings
from ....core.errors import NoActiveProfileError, get_registered_error_code
from ....tests.secure_sql import isolated_runtime_profile
from .._models import WorkflowState
from .._profile_bucket_scan import resolve_profile_bucket

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_resolver_returns_none_when_no_rung_resolves(tmp_path: Path) -> None:
    """A fresh root with no env override + no pointer yields None."""

    with override_settings(aeat_active_profile=None, aeat_local_storage_root=tmp_path):
        assert resolve_active_bucket_id() is None


def test_pointer_file_wins_when_only_rung_two_is_set(tmp_path: Path) -> None:
    """With no env override, the pointer file is the canonical default."""

    write_pointer(tmp_path, BucketPointer(bucket_id="catering", schema_version=1))

    with override_settings(aeat_active_profile=None, aeat_local_storage_root=tmp_path):
        assert resolve_active_bucket_id() == "catering"


def test_settings_override_wins_over_pointer_file(tmp_path: Path) -> None:
    """Rung one (Settings) takes precedence over rung two (pointer)."""

    write_pointer(tmp_path, BucketPointer(bucket_id="catering", schema_version=1))

    with override_settings(aeat_active_profile="translation", aeat_local_storage_root=tmp_path):
        assert resolve_active_bucket_id() == "translation"


def test_empty_settings_override_falls_through_to_pointer(tmp_path: Path) -> None:
    """An empty override (whitespace) does not block rung two."""

    write_pointer(tmp_path, BucketPointer(bucket_id="catering", schema_version=1))

    with override_settings(aeat_active_profile="   ", aeat_local_storage_root=tmp_path):
        assert resolve_active_bucket_id() == "catering"


def test_no_active_profile_error_has_registered_error_code() -> None:
    """The workflow no-active-profile export must bind to the relocated core error."""

    code = get_registered_error_code(NoActiveProfileError)
    assert code.code == "REFUSED_NO_ACTIVE_PROFILE"
    assert code.message_key == "errors.refused.refused_no_active_profile"


def test_active_profile_record_logs_missing_secure_record(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """A missing active secure profile record returns None but is not silent."""

    bucket_id = "missing-record-profile"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        caplog.set_level(logging.DEBUG, logger="aeat.application.workflow._models")

        assert WorkflowState().active_profile_record() is None

    assert "active profile record resolution returned no profile record: ProfileNotFoundError" in caplog.text
    assert bucket_id not in caplog.text


def _write_live_bucket(root: Path, *, bucket_id: str, label: str) -> None:
    """Write a real live bucket manifest at ``<root>/buckets/<bucket_id>/``.

    No mock: a plaintext ``manifest.toml`` carrying the immutable UUID
    ``bucket_id`` and the operator ``label``, exactly as ``profile create``
    materialises it.
    """
    from datetime import UTC, datetime

    from ....adapters.persistence.storage.bucket import (
        BucketLifecycleStatus,
        BucketManifest,
        bucket_paths,
        provision_bucket_directory,
        write_manifest,
    )
    from ....adapters.persistence.storage.master_key import KdfParams

    now = datetime.now(UTC).replace(microsecond=0)
    provision_bucket_directory(root, bucket_id)
    write_manifest(
        bucket_paths(root, bucket_id),
        BucketManifest(
            bucket_id=bucket_id,
            label=label,
            created_at=now,
            last_unlocked_at=None,
            kdf_params=KdfParams.default().to_manifest_params(),
            recovery_enrolled=False,
            schema_version=1,
            status=BucketLifecycleStatus.ACTIVE,
        ),
    )


def test_resolve_profile_bucket_resolves_an_active_profile_by_uuid(tmp_path: Path) -> None:
    """A UUID identifier resolves directly to its bucket pointer."""

    uuid = "51c1fa97-28e1-4700-ac1e-ed7cf094d37b"
    _write_live_bucket(tmp_path, bucket_id=uuid, label="operator")

    pointer = resolve_profile_bucket(uuid, root=tmp_path)

    assert pointer is not None
    assert pointer.bucket_id == uuid
    assert pointer.label == "operator"


def test_resolve_profile_bucket_resolves_an_active_profile_by_display_name(tmp_path: Path) -> None:
    """A display-name identifier resolves to the UUID bucket via the label fallback.

    This is the real operator path: ``AEAT_ACTIVE_PROFILE=operator`` (or any
    active-profile pointer carrying the operator label the user chose at
    ``profile create``, never the UUID they never see). The by-UUID-direct
    lookup misses on the label, so resolution falls back to the
    manifest-scan-by-label and returns the correct bucket. Without the
    fallback this raises a "no manifest" / "unknown profile" refusal on every
    profile-scoped command.
    """

    uuid = "51c1fa97-28e1-4700-ac1e-ed7cf094d37b"
    _write_live_bucket(tmp_path, bucket_id=uuid, label="operator")

    pointer = resolve_profile_bucket("operator", root=tmp_path)

    assert pointer is not None
    assert pointer.bucket_id == uuid, "the display name must resolve to the immutable UUID bucket id"
    assert pointer.label == "operator"


def test_resolve_profile_bucket_returns_none_for_an_unknown_identifier(tmp_path: Path) -> None:
    """Neither a UUID-shaped nor a label-shaped unknown identifier resolves."""

    _write_live_bucket(tmp_path, bucket_id="51c1fa97-28e1-4700-ac1e-ed7cf094d37b", label="operator")

    assert resolve_profile_bucket("nonexistent", root=tmp_path) is None


def test_resolve_profile_bucket_raises_on_an_ambiguous_label(tmp_path: Path) -> None:
    """Two live buckets sharing a label raise ProfileLabelAmbiguousError, never a pick.

    A wrong silent pick on a tax profile is a data-integrity hazard, so the
    label fallback refuses an ambiguous label rather than choosing one bucket.
    The raised type is ProfileLabelAmbiguousError — a WorkflowError, NOT a
    ValueError — which the CLI / diagnostics catch sites must match exactly to
    surface a clean refusal instead of a raw traceback.
    """
    from .._errors import ProfileLabelAmbiguousError

    _write_live_bucket(tmp_path, bucket_id="51c1fa97-28e1-4700-ac1e-ed7cf094d37b", label="operator")
    _write_live_bucket(tmp_path, bucket_id="62d2ab08-39f2-4811-bd2a-fe48fd105e4a", label="operator")

    assert not issubclass(ProfileLabelAmbiguousError, ValueError), (
        "ProfileLabelAmbiguousError is NOT a ValueError; `except ValueError` would not catch it"
    )
    with pytest.raises(ProfileLabelAmbiguousError):
        resolve_profile_bucket("operator", root=tmp_path)
