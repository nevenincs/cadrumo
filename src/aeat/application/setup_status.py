"""Application-owned setup readiness and next-action projection."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .profile import validate_profile
from .user_cli import UserCliState


class SetupStatusReport(BaseModel):
    """Current setup readiness state for the operator-facing CLI."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    active_profile: str | None
    profile_ready: bool
    missing_required: tuple[str, ...] = ()
    auth_provider: str
    login_ready: bool
    next_action: str


def build_setup_status(state: UserCliState) -> SetupStatusReport:
    """Return setup readiness and next action for the current user CLI state."""

    record = state.active_profile_record()
    profile_ready = False
    missing_required: tuple[str, ...] = ()
    if record is not None:
        validation = validate_profile(record.values)
        profile_ready = validation.valid
        missing_required = validation.missing_required

    auth_provider = state.auth.provider or ""
    login_ready = state.auth.authenticated_at is not None
    return SetupStatusReport(
        active_profile=state.active_profile,
        profile_ready=profile_ready,
        missing_required=missing_required,
        auth_provider=auth_provider,
        login_ready=login_ready,
        next_action=_next_setup_action(
            has_profile=record is not None,
            missing_required=missing_required,
            auth_provider=auth_provider,
            login_ready=login_ready,
        ),
    )


def _next_setup_action(
    *,
    has_profile: bool,
    missing_required: tuple[str, ...],
    auth_provider: str,
    login_ready: bool,
) -> str:
    if not has_profile:
        return "aeat setup init --name NAME"
    if missing_required:
        return f"aeat setup profile set {missing_required[0]} VALUE"
    if not auth_provider:
        return "aeat setup auth configure --provider certificate --file PATH"
    if not login_ready:
        return "aeat setup auth login"
    return "aeat app overview status"


__all__ = [
    "SetupStatusReport",
    "build_setup_status",
]
