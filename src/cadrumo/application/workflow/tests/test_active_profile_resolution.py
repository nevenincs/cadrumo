"""Precedence-chain tests for the active-profile resolver.

The resolver lives at `cadrumo.core.resolve_active_bucket_id`. It consults
two precedence rungs in order:

1. `Settings.cadrumo_active_profile` (`CADRUMO_ACTIVE_PROFILE` env var, or
   an `override_settings(cadrumo_active_profile=...)` context manager).
2. The plaintext `<cadrumo-root>/active-profile` pointer file written
   by `register_active_profile` / `select_profile`.

A missing pointer + missing env override returns `None` so callers
that surface it to the operator can refuse with a typed
`NoActiveProfileError`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core import BucketPointer, pointer_path, read_pointer, resolve_active_bucket_id, write_pointer
from ....core.config import override_settings
from ....core.errors import NoActiveProfileError, get_registered_error_code
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ... import wizard as _wizard  # noqa: F401
from ...user_profile import UserProfileLifecycleRepository
from .._models import WorkflowState
from .._profile_bucket_scan import resolve_profile_bucket
from .._profile_health import assess_active_profile_health, repair_active_profile_pointer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MANIFEST_CREATED_AT = datetime(2026, 5, 25, 13, 45, 0, tzinfo=UTC)


def test_workflow_models_do_not_expose_active_bucket_resolver_shims() -> None:
    """Workflow models must not be an alternate import path for core resolvers."""

    from .. import _models as workflow_models

    assert not hasattr(workflow_models, "resolve_active_bucket_id")
    assert not hasattr(workflow_models, "require_active_bucket_id")


def test_resolver_uses_active_profile_precedence_chain(tmp_path: Path) -> None:
    """Settings override wins over the active-profile pointer; blank settings fall through."""
    cases = (
        (None, None, None),
        (None, "catering", "catering"),
        ("translation", "catering", "translation"),
        ("   ", "catering", "catering"),
    )

    for index, (settings_profile, pointer_bucket_id, expected_bucket_id) in enumerate(cases):
        case_root = tmp_path / f"precedence-{index}"
        case_root.mkdir()
        if pointer_bucket_id is not None:
            write_pointer(case_root, BucketPointer(bucket_id=pointer_bucket_id, schema_version=1))

        with override_settings(cadrumo_active_profile=settings_profile, cadrumo_local_storage_root=case_root):
            assert resolve_active_bucket_id() == expected_bucket_id


def test_no_active_profile_error_has_registered_error_code() -> None:
    """The workflow no-active-profile export must bind to the relocated core error."""

    code = get_registered_error_code(NoActiveProfileError)
    assert code.code == "REFUSED_NO_ACTIVE_PROFILE"
    assert code.message_key == "errors.refused.refused_no_active_profile"


def test_active_profile_record_logs_missing_secure_record(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """A missing active secure profile record returns None but is not silent."""

    bucket_id = "missing-record-profile"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        caplog.set_level(logging.DEBUG, logger="cadrumo.application.workflow._models")

        assert WorkflowState().active_profile_record() is None

    assert "active profile record resolution returned no profile record: ProfileNotFoundError" in caplog.text
    assert bucket_id not in caplog.text


def test_label_override_resolves_real_record_and_masks_dangling_pointer_repair(tmp_path: Path) -> None:
    """Canonicalize an override label before secure reads while preserving pointer precedence."""

    bucket_id = "51c1fa97-28e1-4700-ac1e-ed7cf094d37b"
    dangling_id = "62d2ab08-39f2-4811-bd2a-fe48fd105e4a"
    record = UserProfileRecord(
        profile_id=bucket_id,
        display_name="Operator",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id, label="Operator") as profile:
        UserProfileLifecycleRepository(bucket_id=bucket_id, objects=profile.repository).save(record)
        write_pointer(profile.storage_root, BucketPointer(bucket_id=dangling_id, schema_version=1))
        target = pointer_path(profile.storage_root)
        dangling_bytes = target.read_bytes()

        with override_settings(cadrumo_active_profile="operator"):
            state = WorkflowState()
            assert state.active_profile_bucket_id() == bucket_id
            assert state.active_profile_record() == record

            protected_health = assess_active_profile_health(state)
            protected_repair = repair_active_profile_pointer(clear_active=True, confirmed=True)

            assert protected_health.active_profile == bucket_id
            assert protected_health.source == "env_override"
            assert protected_health.status == "ready"
            assert protected_health.registered_bucket is True
            assert protected_health.profile_record_present is True
            assert protected_health.repairable_by_clearing_pointer is False
            assert protected_repair.dry_run is True
            assert protected_repair.cleared_pointer is False
            assert target.read_bytes() == dangling_bytes

        with override_settings(cadrumo_active_profile=None):
            exposed_health = assess_active_profile_health()
            repaired = repair_active_profile_pointer(clear_active=True, confirmed=True)

        assert exposed_health.active_profile == dangling_id
        assert exposed_health.source == "pointer"
        assert exposed_health.status == "dangling_pointer"
        assert exposed_health.repairable_by_clearing_pointer is True
        assert repaired.before == exposed_health
        assert repaired.dry_run is False
        assert repaired.cleared_pointer is True
        assert repaired.after is not None
        assert repaired.after.status == "none"
        assert read_pointer(profile.storage_root) is None


def _write_live_bucket(root: Path, *, bucket_id: str, label: str) -> None:
    """Write a real live bucket manifest at ``<root>/buckets/<bucket_id>/``.

    No mock: a plaintext ``manifest.toml`` carrying the immutable UUID
    ``bucket_id`` and the operator ``label``, exactly as ``profile create``
    materialises it.
    """
    from ....adapters.persistence.storage.bucket import (
        BUCKET_MANIFEST_SCHEMA_VERSION,
        BucketManifest,
        bucket_paths,
        provision_bucket_directory,
        write_manifest,
    )
    from ....adapters.persistence.storage.master_key import KdfParams
    from ....domain.user_profile import UserProfileStatus

    provision_bucket_directory(root, bucket_id)
    write_manifest(
        bucket_paths(root, bucket_id),
        BucketManifest(
            bucket_id=bucket_id,
            label=label,
            created_at=_MANIFEST_CREATED_AT,
            last_unlocked_at=None,
            kdf_params=KdfParams.default().to_manifest_params(),
            recovery_enrolled=False,
            schema_version=BUCKET_MANIFEST_SCHEMA_VERSION,
            status=UserProfileStatus.ACTIVE,
        ),
    )


def _tombstone_bucket(root: Path, *, bucket_id: str, label: str) -> None:
    """Write a real tombstoned bucket manifest at ``<root>/buckets/<bucket_id>/``."""
    from ....adapters.persistence.storage.bucket import (
        BUCKET_MANIFEST_SCHEMA_VERSION,
        BucketManifest,
        bucket_paths,
        provision_bucket_directory,
        write_manifest,
    )
    from ....adapters.persistence.storage.master_key import KdfParams
    from ....domain.user_profile import UserProfileStatus

    provision_bucket_directory(root, bucket_id)
    write_manifest(
        bucket_paths(root, bucket_id),
        BucketManifest(
            bucket_id=bucket_id,
            label=label,
            created_at=_MANIFEST_CREATED_AT,
            last_unlocked_at=None,
            kdf_params=KdfParams.default().to_manifest_params(),
            recovery_enrolled=False,
            schema_version=BUCKET_MANIFEST_SCHEMA_VERSION,
            status=UserProfileStatus.TOMBSTONED,
        ),
    )


def test_resolve_profile_bucket_uuid_respects_lifecycle_filter(tmp_path: Path) -> None:
    """UUID resolution respects the live-surface lifecycle filter."""
    cases: tuple[tuple[Callable[..., None], bool, bool], ...] = (
        (_write_live_bucket, False, True),
        (_tombstone_bucket, False, False),
        (_tombstone_bucket, True, True),
    )

    for index, (bucket_writer, include_tombstoned, expected_found) in enumerate(cases):
        case_root = tmp_path / f"lifecycle-{index}"
        uuid = "51c1fa97-28e1-4700-ac1e-ed7cf094d37b"
        bucket_writer(case_root, bucket_id=uuid, label="operator")

        pointer = resolve_profile_bucket(uuid, root=case_root, include_tombstoned=include_tombstoned)

        if expected_found:
            assert pointer is not None
            assert pointer.bucket_id == uuid
            assert pointer.label == "operator"
        else:
            assert pointer is None


def test_resolve_profile_bucket_resolves_an_active_profile_by_display_name(tmp_path: Path) -> None:
    """A display-name identifier resolves to the UUID bucket via the label fallback.

    This is the real operator path: ``CADRUMO_ACTIVE_PROFILE=operator`` (or any
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
