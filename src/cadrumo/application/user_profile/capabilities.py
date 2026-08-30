"""Profile-linked service-capability resolution.

A capability is the operator's opt-in/opt-out of an external service, stored as a
boolean fact under the profile schema ``capabilities`` section of the
:class:`UserProfileRecord`. This module resolves the *effective* posture by
overlaying that profile fact onto the global
``Settings`` default and the global safety floor, returning a typed
:class:`CapabilityDecision` with the reason.

The load-bearing invariant: a capability may only NARROW the global safety
floor, never widen it. The resolver is the single place this is computed; every
gate routes through it.

``cloud_evidence_upload`` is the one capability carrying an absolute
safety-floor bar: gestor mode refuses it regardless of any profile opt-in,
because a gestor never transmits a client's document. It is also the standing
ELIGIBILITY bar for the off-host evidence read — a layer above the
per-invocation acknowledgement — and
:func:`cloud_evidence_upload_eligible_for_active_profile` is the single
production reading of it that every consent-offering surface must route
through. While the bar is off, :func:`~llm.mint_evidence_consent_token` refuses,
so no surface can offer a gate that could succeed.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from ...core import ServiceCapability
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.config import Settings, load_settings
from ...core.parsing import parse_bool
from ...domain.user_profile.values import UserProfileRecord
from .custody_ports import profile_is_persistence_failure
from .login_session_port import profile_current_bucket_session
from .projections import record_to_path_values

__all__ = [
    "CapabilityDecision",
    "CapabilitySource",
    "cloud_evidence_upload_eligible_for_active_profile",
    "resolve_active_capability",
    "resolve_capability",
]

#: Capabilities the global safety floor bars outright, whatever the profile
#: fact says. Derived membership rather than an inline literal so the bar is
#: one declaration the resolver and its gate both read: a member added here is
#: gestor-barred everywhere the resolver runs, and there is no second list to
#: forget.
GESTOR_BARRED_CAPABILITIES = frozenset({ServiceCapability.CLOUD_EVIDENCE_UPLOAD})


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
    """Parse a string-rendered boolean profile fact, or ``None`` when unset/unknown.

    Delegates to the canonical parser the profile WRITE door already validates
    with, so a value the taxpayer was allowed to store is a value this can read.
    A private token set here decides capability posture -- including whether
    sensitive evidence may leave the machine -- against a vocabulary the door
    never agreed to, and the two drifted in both directions:

    * The door accepts ``sí``/``si``/``s``/``verdadero``/``n``/``falso`` (its
      refusal message names ``true/false, sí/no, 1/0`` explicitly, so the
      taxpayer is TOLD to use them) while the private set recognised none of
      them. An answer stored in Spanish read as *unset*, and an unset fact
      falls through to the global deployment flag -- so an explicit opt-OUT of
      cloud evidence upload was silently replaced by the deployment default,
      and the decision recorded ``GLOBAL_SETTING``/"no profile opt-in" when a
      profile opt-out existed.
    * The private set accepted ``on``/``off``, which the door REFUSES outright
      (``boolean_field_invalid``). Those tokens could never reach a stored
      fact, so nothing is lost by dropping them.
    """
    return parse_bool(value)


def resolve_capability(
    capability: ServiceCapability,
    *,
    profile_record: UserProfileRecord | None,
    settings: Settings,
) -> CapabilityDecision:
    """Resolve ``capability`` for a :class:`UserProfileRecord` against the global posture.

    Pure: no I/O. Reads the profile's capability fact (when present), falls back to
    the conservative capability default, and applies the global safety floor on
    top. The safety floor can only DISABLE, never enable.

    Returns:
        The resolved :class:`CapabilityDecision` carrying the posture and reason.
    """
    # The floor is applied FIRST and returns, so a profile opt-in cannot even be
    # read into the decision for a barred capability -- the "opted in" branch is
    # unreachable rather than overridden, which is the difference between a bar
    # and a strong default.
    if capability in GESTOR_BARRED_CAPABILITIES and settings.cadrumo_evidence_gestor_mode:
        return CapabilityDecision(
            capability=capability,
            enabled=False,
            source=CapabilitySource.SAFETY_FLOOR,
            reason=f"{capability.value} is barred in gestor mode: a gestor never transmits a client's document",
        )
    # llm_vision / google_export: profile fact, else the conservative default. No
    # safety-floor bar — vision is on-host, google export is non-sensitive.
    values = record_to_path_values(profile_record) if profile_record is not None else {}
    fact = _parse_bool_fact(values.get(capability.schema_path))
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


def cloud_evidence_upload_eligible_for_active_profile(*, settings: Settings | None = None) -> bool:
    """Whether the active profile is eligible to be OFFERED the off-host consent gate.

    The standing per-profile bar, distinct from the per-invocation
    acknowledgement it sits above: eligibility asks "may this profile ever be
    asked", the acknowledgement asks "does the operator agree to this one read".
    Default off (:attr:`~core.ServiceCapability.CLOUD_EVIDENCE_UPLOAD` is the one
    capability defaulting off) and gestor-barred outright, so the answer here is
    ``False`` on an untouched deployment.

    This is the SINGLE production reading of the bar. Every surface that would
    offer the operator an off-host acknowledgement passes this function's result
    into :func:`~llm.mint_evidence_consent_token`, which refuses when it is
    ``False`` — so "the gate is never offered while the bar is off" is a property
    of the minting path rather than of each surface remembering to hide a prompt.
    A surface that skipped the check would still be unable to obtain a token.

    Args:
        settings: Optional resolved settings override; loaded when omitted.

    Returns:
        ``True`` only when the profile's resolved capability posture permits it.
    """
    return resolve_active_capability(ServiceCapability.CLOUD_EVIDENCE_UPLOAD, settings=settings).enabled


def _active_profile_record() -> UserProfileRecord | None:
    """Return the active profile's record, or ``None`` when unavailable.

    Returns ``None`` — never raises — when there is no active session OR the secret
    store cannot be opened (e.g. a locked store with no passphrase, as on a fresh
    workstation running ``aeat config check``). A diagnostic/gate resolves to the
    conservative global default rather than crashing when the profile is locked.
    """
    try:
        if profile_current_bucket_session() is None:
            return None
        from ..workflow.persistence import workflow_state_repository

        return workflow_state_repository().load().active_profile_record()
    except Exception as exc:
        if profile_is_persistence_failure(exc):
            return None
        raise
