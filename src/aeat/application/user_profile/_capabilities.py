"""Profile-linked service-capability resolution.

A capability is the operator's opt-in/opt-out of an external service, stored as a
boolean fact under the profile schema ``capabilities`` section of the
:class:`UserProfileRecord`. This module resolves the *effective* posture by
overlaying that profile fact onto the global
``Settings`` default and the global safety floor, returning a typed
:class:`CapabilityDecision` with the reason.

The load-bearing invariant (``service-capabilities`` ADR): a capability may only
NARROW the global safety floor, never widen it. For ``cloud_evidence_upload`` the
gestor-mode bar is applied FIRST and absolutely — no profile opt-in can re-enable
cloud upload for a gestor deployment. The resolver is the single place this is
computed; every gate routes through it.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG, ServiceCapability
from ...core.config import Settings, load_settings
from ...domain.user_profile import UserProfileRecord
from ._orchestration import fact_value

__all__ = [
    "CapabilityDecision",
    "CapabilitySource",
    "resolve_active_capability",
    "resolve_capability",
]

_TRUE_TOKENS = frozenset({"true", "1", "yes", "on"})
_FALSE_TOKENS = frozenset({"false", "0", "no", "off"})


class CapabilitySource(StrEnum):
    """Why a capability resolved the way it did."""

    PROFILE = "profile"  # the active profile set an explicit opt-in/out fact
    DEFAULT = "default"  # no profile fact; the conservative capability default applied
    GLOBAL_SETTING = "global_setting"  # no profile fact; the global Settings flag applied
    SAFETY_FLOOR = "safety_floor"  # the global safety floor (gestor mode) barred it absolutely


class CapabilityDecision(BaseModel):
    """The resolved posture of one service capability for a profile."""

    model_config = STRICT_FROZEN_CONFIG

    capability: ServiceCapability
    enabled: bool
    source: CapabilitySource
    reason: str


def _parse_bool_fact(value: str | None) -> bool | None:
    """Parse a string-rendered boolean profile fact, or ``None`` when unset/unknown."""
    if value is None:
        return None
    token = value.strip().casefold()
    if token in _TRUE_TOKENS:
        return True
    if token in _FALSE_TOKENS:
        return False
    return None


def resolve_capability(
    capability: ServiceCapability,
    *,
    profile_record: UserProfileRecord | None,
    settings: Settings,
) -> CapabilityDecision:
    """Resolve ``capability`` for a :class:`UserProfileRecord` against the global posture.

    Pure: no I/O. Reads the profile's capability fact (when present), falls back to
    the global ``Settings`` flag (cloud upload) or the conservative capability
    default (vision / google), and applies the global safety floor on top. The
    safety floor can only DISABLE, never enable.

    Returns:
        The resolved :class:`CapabilityDecision` carrying the posture and reason.
    """
    if capability is ServiceCapability.CLOUD_EVIDENCE_UPLOAD:
        # The gestor bar is absolute and applied first: no profile opt-in re-enables it.
        if settings.aeat_evidence_gestor_mode:
            return CapabilityDecision(
                capability=capability,
                enabled=False,
                source=CapabilitySource.SAFETY_FLOOR,
                reason="gestor mode bars cloud evidence upload for this deployment",
            )
        fact = _parse_bool_fact(fact_value(profile_record, capability.schema_path))
        if fact is not None:
            return CapabilityDecision(
                capability=capability,
                enabled=fact,
                source=CapabilitySource.PROFILE,
                reason=(
                    "profile opted in to cloud evidence upload"
                    if fact
                    else "profile opted out of cloud evidence upload"
                ),
            )
        # No profile fact: the global deployment flag is the fallback default.
        enabled = settings.aeat_evidence_cloud_upload_permitted
        return CapabilityDecision(
            capability=capability,
            enabled=enabled,
            source=CapabilitySource.GLOBAL_SETTING,
            reason=(
                "global aeat_evidence_cloud_upload_permitted is set"
                if enabled
                else "cloud evidence upload is off by default (no profile opt-in, global flag unset)"
            ),
        )

    # llm_vision / google_export: profile fact, else the conservative default. No
    # safety-floor bar — vision is on-host, google export is non-sensitive.
    fact = _parse_bool_fact(fact_value(profile_record, capability.schema_path))
    if fact is not None:
        return CapabilityDecision(
            capability=capability,
            enabled=fact,
            source=CapabilitySource.PROFILE,
            reason=(f"profile opted {'in to' if fact else 'out of'} {capability.value}"),
        )
    return CapabilityDecision(
        capability=capability,
        enabled=capability.default_enabled,
        source=CapabilitySource.DEFAULT,
        reason=f"{capability.value} is {'on' if capability.default_enabled else 'off'} by default (no profile opt-in)",
    )


def resolve_active_capability(
    capability: ServiceCapability,
    *,
    settings: Settings | None = None,
) -> CapabilityDecision:
    """Resolve ``capability`` for the active profile (or the global default when none).

    Loads the active-profile record through a pure read of workflow state (no
    mutation, no bucket events), mirroring the output-language resolver. With no
    active profile, ``profile_record`` is ``None`` and the resolver falls back to
    the global default — so the posture is well-defined even before a profile is
    selected.

    Returns:
        The resolved :class:`CapabilityDecision` for the active profile.
    """
    resolved_settings = settings if settings is not None else load_settings()
    record = _active_profile_record()
    return resolve_capability(capability, profile_record=record, settings=resolved_settings)


def _active_profile_record() -> UserProfileRecord | None:
    """Return the active profile's record, or ``None`` when unavailable.

    Returns ``None`` — never raises — when there is no active session OR the secret
    store cannot be opened (e.g. a locked store with no passphrase, as on a fresh
    workstation running ``aeat config check``). A diagnostic/gate resolves to the
    conservative global default rather than crashing when the profile is locked.
    """
    from ...adapters.persistence.storage import has_active_bucket_session
    from ...adapters.persistence.storage.errors import PersistenceError

    try:
        if not has_active_bucket_session():
            return None
        from ..workflow._persistence import workflow_state_repository

        return workflow_state_repository().load().active_profile_record()
    except PersistenceError:
        return None
