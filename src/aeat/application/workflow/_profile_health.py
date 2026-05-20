"""Active-profile health projection shared by status, auth, and repair surfaces."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from ...core._bucket_pointer_io import pointer_path, read_pointer
from ...core.config import load_settings
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

    registered_pointer = read_profile_bucket_by_id(active_profile)
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
    "assess_active_profile_health",
    "repair_active_profile_pointer",
]
