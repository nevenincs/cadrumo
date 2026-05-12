"""Application-owned setup readiness and next-action projection."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .profile import list_profile_key_records, validate_profile
from .workflow import WorkflowState

_ENROLMENT_KEY = "iva.regime"
"""Profile key whose presence flips the operator profile from ``identity-only``
into ``ready-to-file``. Without an IVA regime declared, the deadline engine
cannot compute IVA obligations, so ``profile_ready`` must NOT report ``true``."""


class SetupStatusReport(BaseModel):
    """Current setup readiness state for the operator-facing CLI."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    active_profile: str | None
    profile_ready: bool
    identity_ready: bool = False
    enrolment_ready: bool = False
    missing_required: tuple[str, ...] = ()
    missing_enrolment: tuple[str, ...] = ()
    profile_present_keys: int
    profile_total_keys: int
    auth_provider: str
    login_ready: bool
    next_action: str


def build_setup_status(state: WorkflowState) -> SetupStatusReport:
    """Return setup readiness and next action for the current user CLI state.

    ``profile_ready`` is true only when both the registry-required keys
    (identity) AND the deadline-engine enrolment keys (regime declaration)
    are present. The audit (UX-006) flagged the previous boolean as
    misleading because it returned ``true`` for a profile carrying just
    the two identity keys -- a state in which no modelo can be filed.
    """

    record = state.active_profile_record()
    identity_ready = False
    missing_required: tuple[str, ...] = ()
    profile_present_keys = 0
    profile_total_keys = len(list_profile_key_records())
    enrolment_ready = False
    missing_enrolment: tuple[str, ...] = ()
    if record is not None:
        validation = validate_profile(record.values)
        identity_ready = validation.valid
        missing_required = validation.missing_required
        profile_present_keys = validation.present_keys
        profile_total_keys = validation.total_keys
        enrolment_value = (record.values.get(_ENROLMENT_KEY) or "").strip()
        enrolment_ready = bool(enrolment_value)
        if not enrolment_ready:
            missing_enrolment = (_ENROLMENT_KEY,)

    profile_ready = identity_ready and enrolment_ready

    auth_provider = state.auth.provider or ""
    login_ready = state.auth.authenticated_at is not None
    return SetupStatusReport(
        active_profile=state.active_profile,
        profile_ready=profile_ready,
        identity_ready=identity_ready,
        enrolment_ready=enrolment_ready,
        missing_required=missing_required,
        missing_enrolment=missing_enrolment,
        profile_present_keys=profile_present_keys,
        profile_total_keys=profile_total_keys,
        auth_provider=auth_provider,
        login_ready=login_ready,
        next_action=_next_setup_action(
            has_profile=record is not None,
            missing_required=missing_required,
            missing_enrolment=missing_enrolment,
            auth_provider=auth_provider,
            login_ready=login_ready,
        ),
    )


def _next_setup_action(
    *,
    has_profile: bool,
    missing_required: tuple[str, ...],
    missing_enrolment: tuple[str, ...],
    auth_provider: str,
    login_ready: bool,
) -> str:
    if not has_profile:
        return "aeat setup init --name NAME"
    if missing_required:
        return f"aeat setup profile set {missing_required[0]} VALUE"
    if missing_enrolment:
        return f"aeat setup profile set {missing_enrolment[0]} general"
    if not auth_provider:
        return "aeat setup auth configure --provider certificate --file PATH"
    if not login_ready:
        return "aeat setup auth login"
    return "aeat app overview status"


__all__ = [
    "SetupStatusReport",
    "build_setup_status",
]
