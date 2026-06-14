"""Active-profile health projection shared by status, auth, and repair surfaces.

:func:`assess_active_profile_health` reads the persisted
:class:`UserProfileRecord` from the active bucket and returns an
:class:`ActiveProfileHealth` verdict used by every operator status surface.
"""

from __future__ import annotations

import tomllib
from typing import Literal

from pydantic import BaseModel, ValidationError

from ...adapters.persistence.storage.bucket import (
    BucketLifecycleStatus,
    BucketManifest,
    bucket_paths,
    manifest_path,
    write_manifest,
)
from ...adapters.persistence.storage.errors import StorageValidationError
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import pointer_path, read_pointer
from ...core.config import load_settings
from ...core.errors import AeatError
from ...core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from ...core.logging import get_logger
from ...domain.user_profile import UserProfileRecord
from ..user_profile._keys_validation import list_profile_key_records, validate_profile_values
from ..user_profile._projections import record_to_path_values
from ._models import WorkflowState
from ._persistence import workflow_state_repository
from ._profile_bucket_scan import read_profile_bucket_by_id

ProfileHealthStatus = Literal[
    "none",
    "dangling_pointer",
    "missing_profile_record",
    "profile_record_unreadable",
    "manifest_unreadable",
    "incomplete",
    "ready",
]

ProfileSource = Literal["none", "env_override", "pointer"]


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


class ActiveProfileManifestStatusRepairResult(BaseModel):
    """Result of a safe manifest lifecycle-status repair probe/action."""

    model_config = _STRICT_FROZEN

    dry_run: bool
    repaired: bool
    before: ActiveProfileHealth
    after: ActiveProfileHealth | None = None
    status: str = ""
    reason: str = ""


_log = get_logger(__name__)

_MANIFEST_HEALTH_EXCEPTIONS = (
    OSError,
    StorageValidationError,
    ValidationError,
    tomllib.TOMLDecodeError,
    TypeError,
    ValueError,
)


def assess_active_profile_health(state: WorkflowState | None = None) -> ActiveProfileHealth:
    """Return a redacted, non-secret :class:`ActiveProfileHealth` projection for the active profile."""
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
    except _MANIFEST_HEALTH_EXCEPTIONS as exc:
        _log.debug(
            "active profile manifest unreadable bucket_id=%s",
            active_profile,
            exc_info=exc,
        )
        return ActiveProfileHealth(
            active_profile=active_profile,
            source=source,
            status="manifest_unreadable",
            registered_bucket=True,
            profile_record_error=_compact_error(exc),
            profile_total_keys=total_keys,
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
    except (AeatError, OSError) as exc:
        # AeatError: decryption, session, or domain failures loading the workflow state row.
        # OSError: filesystem I/O failure reading the encrypted database file.
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
    except (AeatError, ValueError) as exc:
        # AeatError: domain or registry failures resolving the profile record.
        # ValueError (including pydantic ValidationError): stored record fails strict validation.
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
            "aeat app overview status" if validation.valid else f"aeat config profile edit {registered_pointer.label}"
        ),
    )


def repair_active_profile_pointer(*, clear_active: bool, confirmed: bool) -> ActiveProfileRepairResult:
    """Clear a degraded pointer-file active profile when explicitly confirmed.

    Returns an :class:`ActiveProfileRepairResult`.
    """
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


def repair_active_profile_manifest_status(*, confirmed: bool) -> ActiveProfileManifestStatusRepairResult:
    """Backfill a legacy active-bucket manifest status from the encrypted record.

    Returns an :class:`ActiveProfileManifestStatusRepairResult` indicating
    whether a repair was performed and the before/after health states.
    """
    before = _assess_with_best_effort_session()
    if before.status != "manifest_unreadable" or before.active_profile is None:
        return ActiveProfileManifestStatusRepairResult(
            dry_run=True,
            repaired=False,
            before=before,
            reason="active profile manifest does not need lifecycle-status repair",
        )
    if not confirmed:
        return ActiveProfileManifestStatusRepairResult(
            dry_run=True,
            repaired=False,
            before=before,
            reason="confirmation required",
        )

    record = _load_active_profile_record()
    status = BucketLifecycleStatus(record.status.value)
    paths = bucket_paths(load_settings().aeat_local_storage_root, before.active_profile)
    payload = dict(tomllib.loads(manifest_path(paths).read_text(encoding=_UTF_8_ENCODING)))
    payload.setdefault("last_unlocked_at", None)
    payload.setdefault("idle_lock_minutes", None)
    payload["status"] = status.value
    manifest = BucketManifest.model_validate(payload)
    write_manifest(paths, manifest)
    return ActiveProfileManifestStatusRepairResult(
        dry_run=False,
        repaired=True,
        before=before,
        after=_assess_with_best_effort_session(),
        status=status.value,
    )


def _load_active_profile_record() -> UserProfileRecord:
    """Load the encrypted active-profile record or raise a precise refusal."""
    state = workflow_state_repository().load()
    record = state.active_profile_record()
    if record is None:
        from ...domain.user_profile import ProfileNotFoundError

        raise ProfileNotFoundError("active profile record is missing; manifest status cannot be repaired")
    return record


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
    except (AeatError, OSError, ImportError) as exc:
        # AeatError: keyring/master-key domain failures.
        # OSError: filesystem-backed secret-store I/O failures.
        # ImportError: defensive guard; the dynamic import of storage internals may fail.
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
    "ActiveProfileManifestStatusRepairResult",
    "ActiveProfileRepairResult",
    "assess_active_profile_health",
    "repair_active_profile_manifest_status",
    "repair_active_profile_pointer",
]
