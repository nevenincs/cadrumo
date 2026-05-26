"""Active-profile health projection shared by status, auth, and repair surfaces."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ...adapters.persistence.storage.bucket._layout import bucket_paths
from ...adapters.persistence.storage.bucket._manifest import BucketLifecycleStatus, BucketManifest
from ...adapters.persistence.storage.bucket._manifest_io import manifest_path, read_manifest, write_manifest
from ...adapters.persistence.storage.errors import StorageValidationError
from ...core._bucket_pointer_io import pointer_path, read_pointer
from ...core.config import load_settings
from ...domain.user_profile import UserProfileStatus
from ..user_profile._keys_validation import list_profile_key_records, validate_profile_values
from ..user_profile._projections import record_to_path_values
from ..user_profile._repository import UserProfileLifecycleRepository
from ._models import WorkflowState
from ._persistence import workflow_state_repository
from ._profile_bucket_scan import read_profile_bucket_by_id

ProfileHealthStatus = Literal[
    "none",
    "dangling_pointer",
    "manifest_unreadable",
    "missing_profile_record",
    "profile_record_unreadable",
    "incomplete",
    "ready",
]

ProfileSource = Literal["none", "env_override", "pointer"]

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class ActiveProfileHealth(BaseModel):
    """Redacted active-profile health snapshot."""

    model_config = _STRICT_FROZEN

    active_profile: str | None
    source: ProfileSource
    status: ProfileHealthStatus
    registered_bucket: bool = False
    profile_record_present: bool = False
    profile_record_error: str = ""
    profile_present_keys: int = 0
    profile_total_keys: int = 0
    missing_required: tuple[str, ...] = ()
    repairable_by_clearing_pointer: bool = False
    next_action: str = ""


class ActiveProfileRepairResult(BaseModel):
    """Result of a safe active-profile repair probe/action."""

    model_config = _STRICT_FROZEN

    dry_run: bool
    cleared_pointer: bool
    before: ActiveProfileHealth
    after: ActiveProfileHealth | None = None


class ManifestStatusRepairResult(BaseModel):
    """Result of a legacy bucket-manifest lifecycle-status repair."""

    model_config = _STRICT_FROZEN

    dry_run: bool
    repaired: bool
    bucket_id: str | None
    status: str | None = None
    reason: str = ""
    before: ActiveProfileHealth
    after: ActiveProfileHealth | None = None


def assess_active_profile_health(state: WorkflowState | None = None) -> ActiveProfileHealth:
    """Return a redacted, non-secret health projection for the active profile."""

    settings = load_settings()
    override = (settings.aeat_active_profile or "").strip()
    pointer = None if override else read_pointer(settings.aeat_local_storage_root)
    active_profile = override or (pointer.bucket_id if pointer is not None else None)
    source: ProfileSource = "env_override" if override else ("pointer" if pointer is not None else "none")
    total_keys = len(list_profile_key_records())
    if active_profile is None:
        return ActiveProfileHealth(
            active_profile=None,
            source=source,
            status="none",
            profile_total_keys=total_keys,
            next_action="aeat config profile create NAME --tax-id <TAX_ID> --activity <ACTIVITY>",
        )

    try:
        registered_pointer = read_profile_bucket_by_id(active_profile)
    except StorageValidationError as exc:
        return ActiveProfileHealth(
            active_profile=active_profile,
            source=source,
            status="manifest_unreadable",
            registered_bucket=False,
            profile_record_error=_compact_error(exc),
            profile_total_keys=total_keys,
            repairable_by_clearing_pointer=False,
            next_action="aeat config repair profile --repair-manifest-status --yes",
        )
    registered = registered_pointer is not None
    if not registered:
        return ActiveProfileHealth(
            active_profile=active_profile,
            source=source,
            status="dangling_pointer",
            registered_bucket=False,
            profile_total_keys=total_keys,
            repairable_by_clearing_pointer=source == "pointer",
            next_action=(
                "aeat config repair profile --clear-active --yes"
                if source == "pointer"
                else "unset AEAT_ACTIVE_PROFILE or set it to a registered profile"
            ),
        )

    try:
        resolved_state = state or workflow_state_repository().load()
    except Exception as exc:
        return ActiveProfileHealth(
            active_profile=active_profile,
            source=source,
            status="profile_record_unreadable",
            registered_bucket=True,
            profile_record_error=_compact_error(exc),
            profile_total_keys=total_keys,
            repairable_by_clearing_pointer=source == "pointer",
            next_action=(
                "aeat config repair profile --clear-active --yes"
                if source == "pointer"
                else "unset AEAT_ACTIVE_PROFILE or switch to a readable profile"
            ),
        )
    try:
        record = resolved_state.active_profile_record()
    except Exception as exc:
        return ActiveProfileHealth(
            active_profile=active_profile,
            source=source,
            status="profile_record_unreadable",
            registered_bucket=True,
            profile_record_error=_compact_error(exc),
            profile_total_keys=total_keys,
            repairable_by_clearing_pointer=source == "pointer",
            next_action=(
                "aeat config repair profile --clear-active --yes"
                if source == "pointer"
                else "unset AEAT_ACTIVE_PROFILE or switch to a readable profile"
            ),
        )
    if record is None:
        return ActiveProfileHealth(
            active_profile=active_profile,
            source=source,
            status="missing_profile_record",
            registered_bucket=True,
            profile_total_keys=total_keys,
            repairable_by_clearing_pointer=source == "pointer",
            next_action=(
                "aeat config repair profile --clear-active --yes"
                if source == "pointer"
                else "unset AEAT_ACTIVE_PROFILE or switch to a readable profile"
            ),
        )

    values = record_to_path_values(record)
    validation = validate_profile_values(values)
    status: ProfileHealthStatus = "ready" if validation.valid else "incomplete"
    return ActiveProfileHealth(
        active_profile=active_profile,
        source=source,
        status=status,
        registered_bucket=True,
        profile_record_present=True,
        profile_present_keys=validation.present_keys,
        profile_total_keys=validation.total_keys,
        missing_required=validation.missing_required,
        next_action=(
            "aeat app overview status"
            if validation.valid
            else f"aeat config profile edit {registered_pointer.label}"
        ),
    )


def repair_active_profile_pointer(*, clear_active: bool, confirmed: bool) -> ActiveProfileRepairResult:
    """Clear a degraded pointer-file active profile when explicitly confirmed."""

    before = _assess_with_best_effort_session()
    should_clear = before.repairable_by_clearing_pointer and before.status in {
        "dangling_pointer",
        "missing_profile_record",
        "profile_record_unreadable",
    }
    if not clear_active or not confirmed or not should_clear:
        return ActiveProfileRepairResult(dry_run=True, cleared_pointer=False, before=before)

    target = pointer_path(load_settings().aeat_local_storage_root)
    if target.is_file():
        target.unlink()
    return ActiveProfileRepairResult(
        dry_run=False,
        cleared_pointer=True,
        before=before,
        after=_assess_with_best_effort_session(),
    )


def repair_active_profile_manifest_status(*, confirmed: bool) -> ManifestStatusRepairResult:
    """Backfill a missing manifest status from the encrypted profile record.

    This is deliberately narrower than ``read_manifest``: normal reads
    still fail closed when ``status`` is absent. Repair parses the legacy
    TOML shape only after the active pointer identifies the target bucket,
    reads the encrypted profile record as the lifecycle authority, verifies
    the UUIDs agree, then rewrites the manifest with the recovered status.
    """

    before = _assess_with_best_effort_session()
    bucket_id = before.active_profile
    if bucket_id is None:
        return ManifestStatusRepairResult(
            dry_run=True,
            repaired=False,
            bucket_id=None,
            reason="no_active_profile",
            before=before,
        )
    settings = load_settings()
    try:
        manifest = read_manifest(bucket_paths(settings.aeat_local_storage_root, bucket_id))
    except StorageValidationError as exc:
        if "lifecycle status" not in str(exc):
            return ManifestStatusRepairResult(
                dry_run=True,
                repaired=False,
                bucket_id=bucket_id,
                reason=_compact_error(exc),
                before=before,
            )
    else:
        return ManifestStatusRepairResult(
            dry_run=True,
            repaired=False,
            bucket_id=bucket_id,
            status=manifest.status.value,
            reason="manifest_status_present",
            before=before,
            after=before,
        )

    repaired_manifest = _manifest_with_authoritative_status(settings.aeat_local_storage_root, bucket_id)
    if not confirmed:
        return ManifestStatusRepairResult(
            dry_run=True,
            repaired=False,
            bucket_id=bucket_id,
            status=repaired_manifest.status.value,
            reason="confirmation_required",
            before=before,
        )
    write_manifest(bucket_paths(settings.aeat_local_storage_root, bucket_id), repaired_manifest)
    return ManifestStatusRepairResult(
        dry_run=False,
        repaired=True,
        bucket_id=bucket_id,
        status=repaired_manifest.status.value,
        reason="status_backfilled_from_profile_record",
        before=before,
        after=_assess_with_best_effort_session(),
    )


def _manifest_with_authoritative_status(root: Path, bucket_id: str) -> BucketManifest:
    paths = bucket_paths(root, bucket_id)
    target = manifest_path(paths)
    payload: dict[str, object] = dict(tomllib.loads(target.read_text(encoding="utf-8")))
    if "status" in payload:
        payload.setdefault("last_unlocked_at", None)
        return BucketManifest.model_validate(payload)
    manifest_bucket_id = str(payload.get("bucket_id", ""))
    if manifest_bucket_id != bucket_id:
        raise StorageValidationError(
            "bucket manifest lifecycle status repair refused: manifest bucket_id does not match directory"
        )
    record = UserProfileLifecycleRepository(bucket_id=bucket_id).load(bucket_id)
    if record.profile_id != bucket_id:
        raise StorageValidationError(
            "bucket manifest lifecycle status repair refused: profile record id does not match directory"
        )
    status = _bucket_status_for(record.status)
    payload.setdefault("last_unlocked_at", None)
    payload["status"] = status.value
    return BucketManifest.model_validate(payload)


def _bucket_status_for(status: UserProfileStatus) -> BucketLifecycleStatus:
    return BucketLifecycleStatus(status.value)


def _assess_with_best_effort_session() -> ActiveProfileHealth:
    """Assess profile health, opening the active bucket session when available."""

    before = assess_active_profile_health()
    if before.status != "profile_record_unreadable" or "NoActiveBucketSessionError" not in before.profile_record_error:
        return before
    try:
        from ...adapters.persistence.storage import get_master_key_provider, has_active_bucket_session

        if has_active_bucket_session():
            return before
        with get_master_key_provider():
            return assess_active_profile_health()
    except Exception as exc:
        return before.model_copy(update={"profile_record_error": _compact_error(exc)})


def _compact_error(exc: Exception) -> str:
    """Return a one-line diagnostic without SQL payload noise."""

    root = getattr(exc, "orig", None)
    if isinstance(root, Exception):
        exc = root
    message = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
    return f"{type(exc).__name__}: {message}"


__all__ = [
    "ActiveProfileHealth",
    "ActiveProfileRepairResult",
    "ManifestStatusRepairResult",
    "assess_active_profile_health",
    "repair_active_profile_manifest_status",
    "repair_active_profile_pointer",
]
