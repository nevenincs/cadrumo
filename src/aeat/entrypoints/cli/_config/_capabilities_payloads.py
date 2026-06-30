"""Typed ``--json`` payload schemas for the profile-capabilities CLI commands.

Each class is a strict
:class:`~aeat.entrypoints.cli._schemas.OutputSchema` subclass registered with
:func:`~aeat.entrypoints.cli._schemas.register_schema` so the JSON-contract gate
enumerates the surface. Field sets match the payload dicts constructed in
:mod:`aeat.entrypoints.cli._config._capabilities_cli` and enter
:class:`~aeat.entrypoints.cli._schemas.SchemaEnvelope` through
:func:`~aeat.entrypoints.cli._common._emit_envelope`.

Capability identifiers come from :class:`~aeat.core.ServiceCapability`; the
resolved posture is computed by
:func:`~aeat.application.user_profile.resolve_active_capability` and the pure
:func:`~aeat.application.user_profile.resolve_capability` resolver.
"""

from __future__ import annotations

from .._schemas import OutputSchema, register_schema


class CapabilityRowPayload(OutputSchema):
    """One resolved capability row for the profile-capabilities show result.

    Nested in
    :class:`~aeat.entrypoints.cli._config._capabilities_payloads.CapabilitiesShowResult`
    and mirrors :class:`~aeat.application.user_profile.CapabilityDecision` after
    the resolver has combined the profile fact, global default, and safety
    floor. ``source`` is the JSON value of
    :class:`~aeat.application.user_profile.CapabilitySource`.
    """

    capability: str
    enabled: bool
    source: str
    reason: str


@register_schema("config.profile.capabilities.show")
class CapabilitiesShowResult(OutputSchema):
    """JSON envelope for ``aeat config profile capabilities show``.

    The resolved posture of every service capability for the active profile,
    each with its source (profile fact / global default / safety-floor bar).
    With no active profile, ``profile_id`` is ``None`` and the resolver reports
    the global/default posture.
    """

    profile_id: str | None = None
    capabilities: list[CapabilityRowPayload] = []


@register_schema("config.profile.capabilities.set")
class CapabilitySetResult(OutputSchema):
    """JSON envelope for ``aeat config profile capabilities set``.

    Reports the boolean profile fact written for one
    :class:`~aeat.core.ServiceCapability`. The mutation goes through the profile
    single-writer path; this payload only echoes the resulting profile id,
    capability id, and enabled flag.
    """

    profile_id: str
    capability: str
    enabled: bool
