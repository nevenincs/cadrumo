"""Typed ``--json`` payload schemas for the profile-capabilities CLI commands.

Each class is a strict
:class:`OutputSchema` subclass registered with
CommandSpec schema authority so the JSON-contract gate
enumerates the surface. Field sets match the payload dicts constructed in
:mod:`_capabilities_cli` and enter
:class:`SchemaEnvelope` through
:func:`_emit_envelope`.

Capability identifiers come from :class:`ServiceCapability`; the
resolved posture is computed by
:func:`resolve_active_capability` and the pure
:func:`resolve_capability` resolver.
"""

from __future__ import annotations

from ....application.user_profile import CapabilitySource
from ....core import ServiceCapability
from ....core.identity import ProfileId
from ....core.json_contract import OutputSchema


class CapabilityRowPayload(OutputSchema):
    """One resolved capability row for the profile-capabilities show result.

    Nested in
    :class:`CapabilitiesShowResult`
    and mirrors :class:`CapabilityDecision` after
    the resolver has combined the profile fact, global default, and safety
    floor. ``source`` is the JSON value of
    :class:`CapabilitySource`.
    """

    capability: ServiceCapability
    enabled: bool
    source: CapabilitySource
    reason: str


class CapabilitiesShowResult(OutputSchema):
    """JSON envelope for ``aeat config profile capabilities show``.

    The resolved posture of every service capability for the active profile,
    each with its source (profile fact / global default / safety-floor bar).
    With no active profile, ``profile_id`` is ``None`` and the resolver reports
    the global/default posture.
    """

    profile_id: ProfileId | None = None
    capabilities: list[CapabilityRowPayload] = []


class CapabilitySetResult(OutputSchema):
    """JSON envelope for ``aeat config profile capabilities set``.

    Reports the boolean profile fact written for one
    :class:`ServiceCapability`. The mutation goes through the profile
    single-writer path; this payload only echoes the resulting profile id,
    capability id, and enabled flag.
    """

    profile_id: ProfileId
    capability: ServiceCapability
    enabled: bool
