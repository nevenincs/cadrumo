"""Typed ``--json`` payload schemas for the profile-capabilities CLI commands.

Each class is a strict :class:`OutputSchema` subclass registered with
:func:`register_schema` so the JSON-contract gate enumerates the surface. Field
sets match the payload dicts constructed in ``_capabilities_cli.py``.
"""

from __future__ import annotations

from .._schemas import OutputSchema, register_schema


class CapabilityRowPayload(OutputSchema):
    """One resolved capability row (nested)."""

    capability: str
    enabled: bool
    source: str
    reason: str


@register_schema("config.profile.capabilities.show")
class CapabilitiesShowResult(OutputSchema):
    """JSON envelope for ``aeat config profile capabilities show``.

    The resolved posture of every service capability for the active profile,
    each with its source (profile fact / global default / safety-floor bar).
    """

    profile_id: str | None = None
    capabilities: list[CapabilityRowPayload] = []


@register_schema("config.profile.capabilities.set")
class CapabilitySetResult(OutputSchema):
    """JSON envelope for ``aeat config profile capabilities set``."""

    profile_id: str
    capability: str
    enabled: bool
